"""documents (P3): forward uploads to submit_document and turn failed validations into concrete
correction requests (FR-025, FR-034). The node never judges a document itself."""

from typing import Any

from agent.graph import Deps, TurnState, document_node, stage_node
from agent.nodes.common import declared_updates, merge, pesos
from agent.nodes.gate import request_gate_if_ready
from agent.questions import document_question, family
from contracts.common import Stage, Status

DOC_ES = {
    "identification": "identificación",
    "income_proof": "comprobante de ingresos",
    "payslip": "recibo de nómina",
    "bank_statement": "estado de cuenta",
    "proof_of_address": "comprobante de domicilio",
    "vehicle_invoice": "factura del auto",
    "other": "otro tipo de documento",
}
FIELD_ES = {
    "full_name": "el nombre", "net_income": "el ingreso neto", "total_deposits": "el total de depósitos",
    "periodicity": "la periodicidad de pago", "valid_until": "la vigencia", "address": "el domicilio",
    "postal_code": "el código postal", "issue_date": "la fecha de emisión", "make": "la marca",
    "model": "el modelo", "year": "el año",
}
EMPLOYMENT_PROOFS_ES = {"payslip": "recibo de nómina", "bank_statement": "estado de cuenta"}


def explain(validation: dict[str, Any]) -> str:
    detail = validation.get("detail") or {}
    reason = detail.get("reason")
    if reason == "low_confidence":
        fields = " y ".join(FIELD_ES.get(f, f) for f in detail.get("fields", []))
        return f"no pude leer bien {fields}; mándalo con buena luz y sin reflejos"
    if reason == "out_of_tolerance":
        return (f"el ingreso que muestra ({pesos(detail['proved_monthly'])} al mes) no coincide con el que me "
                f"dijiste ({pesos(detail['declared_monthly'])} al mes)")
    if reason == "currency_mismatch":
        return f"está en otra moneda ({detail.get('proof_currency')})"
    if reason == "name_mismatch":
        return "el nombre no coincide con el tuyo"
    if reason == "address_mismatch":
        return "el domicilio no coincide con el que me diste"
    if reason == "postal_code_mismatch":
        return "el código postal no coincide con el que me diste"
    if reason == "expired":
        return "la identificación está vencida"
    if reason == "too_old":
        return f"tiene más de {detail.get('max_age_months', 3)} meses"
    if reason == "proof_not_accepted":
        accepted = " o ".join(EMPLOYMENT_PROOFS_ES.get(a, a) for a in detail.get("accepted", []))
        return f"para tu situación laboral necesito {accepted}"
    if reason == "holder_mismatch":
        return "la factura no está a tu nombre"
    if reason == "vehicle_mismatch":
        return f"la factura es de un {detail.get('invoice')} y me dijiste que tu auto es un {detail.get('declared')}"
    return "no pasó la validación"


@document_node
async def documents(state: TurnState, deps: Deps) -> dict[str, Any]:
    st: dict[str, Any] = dict(state)
    document = state.get("document") or {}
    requested = document.get("requested_type", "other")
    facts = dict(st.get("facts") or {})
    _, updates = await deps.call_tool(
        st, "append_message",
        {"message_id": st["message_id"], "author": "client", "text": f"[documento {requested}: {document.get('filename')}]"},
    )
    st = merge(st, updates)
    if st["case"]["status"] != Status.active or st["case"]["stage"] != Stage.documents:
        facts["note_es"] = "Por ahora no necesito documentos."
        st["facts"] = facts
        return st

    result, updates = await deps.call_tool(st, "submit_document", document)
    st = merge(st, updates)
    if st["case"]["status"] not in (Status.active, Status.ok_for_lender):
        return st  # escalated: respond tells the client an advisor will take the case
    doc_es = DOC_ES.get(family(requested), requested)
    if result.result.get("unexpected_type"):
        detected = DOC_ES.get(result.result.get("detected_type"), "otro documento")
        facts["note_es"] = f"El documento que enviaste parece ser {detected}, pero te pedí tu {doc_es}."
        st["next_question"] = document_question(requested).text
    else:
        failed = [v for v in result.result.get("validations", []) if v["result"] != "passed"]
        if failed:
            reasons = "; ".join(dict.fromkeys(explain(v) for v in failed))
            facts["note_es"] = f"Revisé tu {doc_es}: {reasons}."
            st["next_question"] = document_question(requested).text
        else:
            facts["note_es"] = f"Recibí tu {doc_es} y está en orden."
    st["facts"] = facts
    return await request_gate_if_ready(st, deps)


@stage_node(Stage.documents)
async def documents_message(state: TurnState, deps: Deps) -> dict[str, Any]:
    """A text message while documents are pending: apply corrections the client declares."""
    st: dict[str, Any] = dict(state)
    data = declared_updates(state.get("fields") or {})
    if data:
        result, updates = await deps.call_tool(st, "update_declared_data", data, on_behalf_of="client")
        st = merge(st, updates)
        if result.result.get("revalidated"):
            st["facts"] = {**(st.get("facts") or {}), "note_es": "Gracias, ya revisé tus documentos con el dato corregido."}
    return st
