"""eligibility node (P1): collect name and vehicle answers, then let the system decide."""

from typing import Any

from agent.graph import Deps, TurnState, stage_node
from agent.nodes.common import declared_updates, merge, rejection_facts
from agent.questions import missing_fields
from contracts.common import Stage

ELIGIBILITY_FIELDS = ("full_name", "make", "model", "year", "own_name", "declared_debt", "spare_key")


@stage_node(Stage.eligibility)
async def eligibility(state: TurnState, deps: Deps) -> dict[str, Any]:
    st: dict[str, Any] = dict(state)
    data = declared_updates(state.get("fields") or {})
    if data:
        _, updates = await deps.call_tool(st, "update_declared_data", data, on_behalf_of="client")
        st = merge(st, updates)

    view = await deps.get_case(st)
    vehicle = view.state.vehicle
    disqualified = vehicle.own_name is False or vehicle.declared_debt is True
    if not disqualified and missing_fields(view, Stage.eligibility):
        return st  # respond asks the next missing question (FR-015: no decision yet)

    result, updates = await deps.call_tool(st, "evaluate_eligibility")
    st = merge(st, updates)
    facts = dict(st.get("facts") or {})
    if result.result.get("eligible"):
        note = "¡Buenas noticias! Tu auto cumple los requisitos para usarlo como garantía."
        if result.result.get("key_quote"):
            note += (
                f" Como no tienes la segunda llave, cotizamos su fabricación en ${result.result['key_quote']} "
                "y ese costo se suma a tu plan de pagos."
            )
        facts["note_es"] = note
    else:
        facts.update(rejection_facts(result))
    st["facts"] = facts
    return st
