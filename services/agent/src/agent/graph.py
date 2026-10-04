"""Agent graph (R-19): entry → interpret → router → stage node → respond.

The router decides only from the classified intent and the stage/status returned by the Case
Actions API, never from text written by the LLM (Principle II).
"""

import importlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from agent.clients import ActionsClient, LlmClient
from contracts.actions import ToolContext, ToolResult
from contracts.case import CaseView
from contracts.common import FINAL_STATUSES, Intent, Status


class TurnState(TypedDict, total=False):
    # per turn (reset by the channel on every call)
    case_id: str
    kind: Literal["start", "message", "document"]
    message_id: str
    text: str | None
    document: dict[str, Any] | None
    case: dict[str, Any]  # {"id", "stage", "status", "version"} as returned by the last tool
    intent: str | None
    fields: dict[str, Any]
    facts: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    next_question: str | None
    step: int
    reply: str
    # kept across turns by the checkpointer
    last_question: str | None
    history: list[dict[str, str]]


Node = Callable[["TurnState", "Deps"], Awaitable[dict[str, Any]]]

STAGE_NODES: dict[str, Node] = {}
INTENT_NODES: dict[str, Node] = {}
DOCUMENT_NODE: dict[str, Node] = {}

# Node modules register themselves on import; later phases add theirs here.
NODE_MODULES: list[str] = [
    "agent.nodes.eligibility",
    "agent.nodes.profiling",
    "agent.nodes.simulation",
    "agent.nodes.documents",
]


def stage_node(stage: str) -> Callable[[Node], Node]:
    def register(fn: Node) -> Node:
        STAGE_NODES[stage] = fn
        return fn

    return register


def intent_node(intent: Intent) -> Callable[[Node], Node]:
    def register(fn: Node) -> Node:
        INTENT_NODES[intent.value] = fn
        return fn

    return register


def document_node(fn: Node) -> Node:
    DOCUMENT_NODE["documents"] = fn
    return fn


@dataclass
class Deps:
    actions: ActionsClient
    llm: LlmClient

    async def call_tool(
        self,
        state: TurnState,
        tool: str,
        tool_input: dict[str, Any] | None = None,
        *,
        on_behalf_of: Literal["client"] | None = None,
    ) -> tuple[ToolResult, dict[str, Any]]:
        """Call a tool with key `(message_id, step, tool)` (R-19); returns the result and state updates."""
        step = state.get("step", 0) + 1
        evidence = state["message_id"] if state.get("kind") != "start" else None
        context = ToolContext(
            case_id=state["case_id"],
            idempotency_key=f"{state['message_id']}:{step}:{tool}",
            expected_version=state["case"]["version"],
            on_behalf_of=on_behalf_of,
            evidence_message_id=evidence,
        )
        result = await self.actions.call(tool, context, tool_input)
        if result.rejection and result.rejection.code == "version_conflict":
            # Someone else (an advisor) changed the case; reread and retry once with a new key.
            view = await self.actions.get_case(state["case_id"])
            context.expected_version = view.version
            context.idempotency_key += ":retry"
            result = await self.actions.call(tool, context, tool_input)
        updates: dict[str, Any] = {
            "step": step,
            "tool_calls": [
                *state.get("tool_calls", []),
                {
                    "tool": tool,
                    "outcome": result.outcome.value,
                    "rejection_code": result.rejection.code if result.rejection else None,
                },
            ],
        }
        if result.case is not None:
            updates["case"] = result.case.model_dump(mode="json")
        return result, updates

    async def get_case(self, state: TurnState) -> CaseView:
        return await self.actions.get_case(state["case_id"])


def route_entry(state: TurnState) -> str:
    if state.get("kind") == "start":
        return "respond"
    if state.get("kind") == "document":
        return "documents" if "documents" in DOCUMENT_NODE else "respond"
    return "interpret"


def route_after_interpret(state: TurnState) -> str:
    status = state["case"]["status"]
    intent = state.get("intent")
    if intent == Intent.cancel and intent in INTENT_NODES and status in (Status.active, Status.escalated):
        return f"intent_{intent}"
    if status != Status.active:
        return "respond"
    if intent in INTENT_NODES:
        return f"intent_{intent}"
    stage = state["case"]["stage"]
    return f"stage_{stage}" if stage in STAGE_NODES else "respond"


def build_graph(deps: Deps, checkpointer: Any = None):
    for module in NODE_MODULES:
        importlib.import_module(module)
    from agent.nodes.interpret import interpret
    from agent.nodes.respond import respond

    def bind(fn: Node) -> Callable[[TurnState], Awaitable[dict[str, Any]]]:
        async def run(state: TurnState) -> dict[str, Any]:
            return await fn(state, deps)

        return run

    graph = StateGraph(TurnState)
    graph.add_node("interpret", bind(interpret))
    graph.add_node("respond", bind(respond))
    targets = {"respond": "respond"}
    for stage, fn in STAGE_NODES.items():
        graph.add_node(f"stage_{stage}", bind(fn))
        graph.add_edge(f"stage_{stage}", "respond")
        targets[f"stage_{stage}"] = f"stage_{stage}"
    for intent, fn in INTENT_NODES.items():
        graph.add_node(f"intent_{intent}", bind(fn))
        graph.add_edge(f"intent_{intent}", "respond")
        targets[f"intent_{intent}"] = f"intent_{intent}"
    entry_targets = {"respond": "respond", "interpret": "interpret"}
    if "documents" in DOCUMENT_NODE:
        graph.add_node("documents", bind(DOCUMENT_NODE["documents"]))
        graph.add_edge("documents", "respond")
        entry_targets["documents"] = "documents"

    graph.add_conditional_edges(START, route_entry, entry_targets)
    graph.add_conditional_edges("interpret", route_after_interpret, targets)
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)


def is_closed(state: TurnState) -> bool:
    return state["case"]["status"] in FINAL_STATUSES
