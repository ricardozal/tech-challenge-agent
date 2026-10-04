"""profiling node (P2): address, employment, income and consent; then the system profiles and simulates."""

from typing import Any

from agent.graph import Deps, TurnState, stage_node
from agent.nodes.common import declared_updates, merge, present_options, rejection_facts
from agent.questions import missing_fields
from contracts.common import Stage, Status

CONSENT_NEEDED = (
    "Sin tu autorización no puedo consultar tu historial en Buró de Crédito, y es necesaria para continuar."
)


@stage_node(Stage.profiling)
async def profiling(state: TurnState, deps: Deps) -> dict[str, Any]:
    st: dict[str, Any] = dict(state)
    fields = state.get("fields") or {}
    facts = dict(st.get("facts") or {})

    data = declared_updates(fields)
    if data:
        _, updates = await deps.call_tool(st, "update_declared_data", data, on_behalf_of="client")
        st = merge(st, updates)
    if fields.get("bureau_consent") is True:
        _, updates = await deps.call_tool(st, "record_bureau_consent", {"consent": True}, on_behalf_of="client")
        st = merge(st, updates)
    elif fields.get("bureau_consent") is False:
        facts["note_es"] = CONSENT_NEEDED

    view = await deps.get_case(st)
    if missing_fields(view, Stage.profiling):
        st["facts"] = facts
        return st  # respond asks the next missing question

    result, updates = await deps.call_tool(st, "run_credit_check")
    st = merge(st, updates)
    if st["case"]["stage"] == Stage.simulation and st["case"]["status"] == Status.active:
        result, updates = await deps.call_tool(st, "simulate_options")
        st = merge(st, updates)
        if result.result.get("options"):
            facts["note_es"] = present_options(result.result["options"])
    facts.update(rejection_facts(result))
    st["facts"] = facts
    return st
