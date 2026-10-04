"""simulation node (P2): the client picks one of the proposed options (FR-024)."""

from typing import Any

from agent.graph import Deps, TurnState, stage_node
from agent.nodes.common import merge, pesos, present_options, rejection_facts
from contracts.common import Stage

ONLY_PROPOSED = (
    "Solo puedo ofrecerte las opciones que te mostré: están calculadas con tu perfil y el valor de tu auto."
)


@stage_node(Stage.simulation)
async def simulation(state: TurnState, deps: Deps) -> dict[str, Any]:
    st: dict[str, Any] = dict(state)
    fields = state.get("fields") or {}
    facts = dict(st.get("facts") or {})

    view = await deps.get_case(st)
    options = [o.model_dump(mode="json") for o in view.state.options]
    if not options:
        result, updates = await deps.call_tool(st, "simulate_options")
        st = merge(st, updates)
        options = result.result.get("options", [])
        facts.update(rejection_facts(result))
        if not options:
            st["facts"] = facts
            return st

    chosen = fields.get("chosen_option")
    if isinstance(chosen, int) and 1 <= chosen <= len(options):
        option = options[chosen - 1]
        result, updates = await deps.call_tool(
            st, "select_option", {"option_id": option["id"]}, on_behalf_of="client"
        )
        st = merge(st, updates)
        if result.outcome == "accepted":
            facts["note_es"] = (
                f"Perfecto, elegiste recibir {pesos(option['client_amount'])} y pagar "
                f"{pesos(option['monthly_payment'])} al mes. Ahora necesito tus documentos."
            )
            st["facts"] = facts
            return st

    asked_other = chosen is not None or fields.get("requested_amount") or fields.get("term_months")
    facts["note_es"] = (ONLY_PROPOSED + " " if asked_other else "") + present_options(options)
    st["facts"] = facts
    return st
