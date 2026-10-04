"""Advisor resolves tickets with the same action layer (FR-043 to FR-046, FR-050)."""

import pytest

from tests.support.cases import documents_case
from tests.support.reader import LOW_PAYSLIP, install, submit

DOCS = ("identification", "proof_of_address", "vehicle_invoice")


def escalated(api, with_other_docs=True):
    reader = install(api)
    case = documents_case(api)
    if with_other_docs:
        for doc in DOCS:
            submit(case, doc)
    reader.overrides["payslip"] = LOW_PAYSLIP
    for _ in range(3):
        submit(case, "payslip")
    assert case.view()["status"] == "escalated"
    return case, reader


def ticket(api, case):
    return [t for t in api.client.get("/escalations").json() if t["case_id"] == case.id][-1]


@pytest.mark.req("FR-044")
@pytest.mark.parametrize(("tool", "payload", "status"), [
    ("request_correction", {"validation_key": "income", "message_to_client": "Envía tu último recibo."}, "active"),
    ("return_to_agent", {"note": "Revisé con el cliente."}, "active"),
    ("reject_case", {"reason": "Ingreso insuficiente confirmado"}, "rejected"),
])
def test_advisor_actions_resolve_the_ticket_and_are_audited(api, tool, payload, status):
    case, _ = escalated(api)
    resp = api.call(tool, case.id, case.version, actor="advisor", key=f"adv-{tool}", input=payload)
    again = api.call(tool, case.id, case.version, actor="advisor", key=f"adv-{tool}", input=payload)  # replay

    assert resp.status_code == 200 and again.json() == resp.json()
    assert case.view()["status"] == status
    assert ticket(api, case)["status"] == "resolved" and ticket(api, case)["resolution"]["actor"] == "advisor"
    entry = [e for e in api.audit(case.id) if e["tool"] == tool]
    assert len(entry) == 1 and entry[0]["actor"] == "advisor"
    if status == "active":
        assert case.view()["state"]["attempts"] == {}  # the counter restarts after a human intervened


@pytest.mark.req("FR-045")
def test_manual_verification_needs_justification_and_reruns_the_gate(api):
    case, _ = escalated(api)
    short = case.call("verify_validation_manually", {"validation_key": "income", "justification": "ok",
                                                     "evidence": ["llamada"]}, actor="advisor")
    assert short.status_code == 422
    by_agent = case.call("verify_validation_manually", {"validation_key": "income", "justification":
                         "Ingreso confirmado por llamada", "evidence": ["llamada"]})
    assert by_agent.status_code == 403

    body = case.call("verify_validation_manually", {"validation_key": "income", "justification":
                     "Ingreso confirmado por llamada con el empleador", "evidence": ["llamada-2026-10-04"]},
                     actor="advisor").json()

    income = case.view()["state"]["validations"]["income"]
    assert income["origin"] == "manual" and income["result"] == "passed"
    assert income["justification"].startswith("Ingreso confirmado")
    assert body["case"]["status"] == "ok_for_lender"  # the system decided, through the gate
    gate = [e for e in api.audit(case.id) if e["tool"] == "evaluate_gate"][-1]
    assert gate["actor"] == "system" and gate["outcome"] == "accepted"
    assert ticket(api, case)["status"] == "resolved"


def test_manual_verification_without_the_other_documents_keeps_the_case_escalated(api):
    case, _ = escalated(api, with_other_docs=False)
    body = case.call("verify_validation_manually", {"validation_key": "income", "justification":
                     "Ingreso confirmado por llamada", "evidence": ["llamada"]}, actor="advisor").json()
    assert body["case"]["status"] == "escalated"


@pytest.mark.req("FR-050")
def test_advisor_revokes_an_ok_and_the_agent_cannot(api):
    case, _ = escalated(api)
    case.call("verify_validation_manually", {"validation_key": "income", "justification":
              "Ingreso confirmado por llamada", "evidence": ["llamada"]}, actor="advisor")
    assert case.view()["status"] == "ok_for_lender"

    assert case.call("revoke_ok", {"reason": "Documento alterado"}).status_code == 403
    body = case.call("revoke_ok", {"reason": "Documento alterado"}, actor="advisor").json()

    assert body["case"]["status"] == "escalated"
    assert {"type": "ok_revoked", "reason": "Documento alterado"} in body["events"]
    assert ticket(api, case)["reason"] == "ok_revoked"


@pytest.mark.req("FR-046")
@pytest.mark.req("FR-043")
def test_client_can_cancel_even_while_escalated_and_the_ticket_closes(api):
    case, _ = escalated(api)
    body = case.call("cancel_case", {"reason": "ya no lo necesito"}, on_behalf_of="client",
                     evidence_message_id="m-cancel").json()
    assert body["case"]["status"] == "cancelled"
    assert ticket(api, case)["status"] == "resolved"


@pytest.mark.req("FR-043")
def test_agent_cannot_request_the_gate_while_escalated(api):
    case, _ = escalated(api)
    assert case.call("evaluate_gate").status_code == 403


@pytest.mark.req("FR-044")
def test_correction_message_is_kept_until_the_agent_delivers_it(api):
    case, _ = escalated(api)
    case.call("request_correction", {"validation_key": "income", "message_to_client":
              "Envía el recibo de la segunda quincena de septiembre."}, actor="advisor")
    assert case.view()["state"]["pending_client_note"] == "Envía el recibo de la segunda quincena de septiembre."

    case.call("append_message", {"message_id": "m-a1", "author": "agent", "text": "…",
                                 "delivers_pending_note": True})
    assert case.view()["state"]["pending_client_note"] is None
