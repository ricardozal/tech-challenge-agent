"""interpret: message → intent + confirmed fields (LLM), then record the message as evidence."""

from typing import Any

from agent.graph import Deps, TurnState
from contracts.llm import ExtractRequest, to_domain


async def interpret(state: TurnState, deps: Deps) -> dict[str, Any]:
    case = state["case"]
    extraction = await deps.llm.extract(
        ExtractRequest(
            schema_name="mensaje",
            stage=case["stage"],
            agent_question=state.get("last_question"),
            text=state["text"] or "",
        )
    )
    message = to_domain(extraction.data)
    _, updates = await deps.call_tool(
        state,
        "append_message",
        {"message_id": state["message_id"], "author": "client", "text": state["text"] or "", "intent": message.intent.value},
    )
    return {**updates, "intent": message.intent.value, "fields": message.fields}
