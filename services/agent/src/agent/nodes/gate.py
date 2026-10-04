"""gate (FR-036, FR-037): the system evaluates the gate on its own after each validation; the agent
only asks for it when nothing is missing and the case is still open, and reports what the system said."""

from typing import Any

from agent.graph import Deps
from agent.nodes.common import merge
from agent.questions import missing_documents
from contracts.common import Stage, Status


async def request_gate_if_ready(state: dict[str, Any], deps: Deps) -> dict[str, Any]:
    case = state["case"]
    if case["status"] != Status.active or case["stage"] != Stage.documents:
        return state
    view = await deps.get_case(state)
    if missing_documents(view):
        return state
    result, updates = await deps.call_tool(state, "evaluate_gate")
    st = merge(state, updates)
    if result.rejection and result.rejection.code == "gate_not_met":
        st["facts"] = {**(st.get("facts") or {}),
                       "note_es": "Todavía falta que se aprueben algunos de tus documentos."}
    return st

