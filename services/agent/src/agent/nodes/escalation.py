"""escalation and cancellation intents (FR-039, FR-040, FR-046). The router sends these here from
the classified intent only; the agent never tries to solve a sensitive topic itself."""

from typing import Any

from agent.graph import Deps, TurnState, intent_node
from agent.nodes.common import merge
from contracts.common import Intent

NOTES = {
    Intent.request_human: ("client_requested_human", "El cliente pidió hablar con una persona.",
                           "Claro, te comunico con un asesor."),
    Intent.sensitive_topic: ("sensitive_topic", "El cliente mencionó un tema sensible; el agente no intentó resolverlo.",
                             "Gracias por contármelo. Prefiero que un asesor te atienda personalmente."),
}


async def _escalate(state: TurnState, deps: Deps, intent: Intent) -> dict[str, Any]:
    reason, agent_note, client_note = NOTES[intent]
    st: dict[str, Any] = dict(state)
    _, updates = await deps.call_tool(st, "escalate", {"reason": reason, "agent_note": agent_note})
    st = merge(st, updates)
    st["facts"] = {**(st.get("facts") or {}), "note_es": client_note}
    return st


@intent_node(Intent.request_human)
async def request_human(state: TurnState, deps: Deps) -> dict[str, Any]:
    return await _escalate(state, deps, Intent.request_human)


@intent_node(Intent.sensitive_topic)
async def sensitive_topic(state: TurnState, deps: Deps) -> dict[str, Any]:
    return await _escalate(state, deps, Intent.sensitive_topic)


@intent_node(Intent.cancel)
async def cancel(state: TurnState, deps: Deps) -> dict[str, Any]:
    st: dict[str, Any] = dict(state)
    _, updates = await deps.call_tool(st, "cancel_case", {"reason": "cliente_cancela"}, on_behalf_of="client")
    return merge(st, updates)
