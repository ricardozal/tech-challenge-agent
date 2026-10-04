"""Escalations: persisting mismatch, client asks for a human, sensitive topic; ticket contents (P4)."""

import pytest

from tests.support.cases import documents_case, profiling_case
from tests.support.reader import LOW_PAYSLIP, install, submit


def escalated_by_mismatch(api):
    reader = install(api)
    reader.overrides["payslip"] = LOW_PAYSLIP
    case = documents_case(api)
    bodies = [submit(case, "payslip").json() for _ in range(3)]
    return case, bodies


@pytest.mark.req("FR-038")
def test_third_failed_result_of_the_same_type_escalates(api):
    case, bodies = escalated_by_mismatch(api)
    assert [b["case"]["status"] for b in bodies] == ["active", "active", "escalated"]
    assert any(e["type"] == "escalated" and e["reason"] == "mismatch_persisted" for e in bodies[-1]["events"])
    assert not any(e["type"] == "gate_failed" for e in bodies[-1]["events"])  # no gate once escalated


@pytest.mark.req("FR-042")
def test_ticket_has_reason_evidence_summary_and_suggested_action(api):
    case, bodies = escalated_by_mismatch(api)
    ticket = api.client.get(f"/escalations/{bodies[-1]['result']['escalation_id']}").json()
    assert ticket["reason"] == "mismatch_persisted" and ticket["status"] == "open"
    assert ticket["evidence"]["validation_type"] == "income"
    assert ticket["evidence"]["failed_validations"][0]["key"] == "income"
    assert len(ticket["evidence"]["documents"]) == 3
    assert "Laura Méndez Rojas" in ticket["summary"] and "income (mismatch, intento 3)" in ticket["summary"]
    assert ticket["suggested_action"].startswith("Revisar la evidencia")


@pytest.mark.req("FR-039")
def test_client_asking_for_a_human_escalates(api):
    case = profiling_case(api)
    body = case.call("escalate", {"reason": "client_requested_human", "agent_note": "Pidió hablar con una persona."},
                     evidence_message_id="m-5").json()
    assert body["case"]["status"] == "escalated"
    ticket = api.client.get(f"/escalations/{body['result']['escalation_id']}").json()
    assert ticket["reason"] == "client_requested_human" and ticket["agent_note"] == "Pidió hablar con una persona."


@pytest.mark.req("FR-040")
def test_sensitive_topic_escalates(api):
    case = profiling_case(api)
    body = case.call("escalate", {"reason": "sensitive_topic", "agent_note": "Mencionó coerción."}).json()
    assert body["case"]["status"] == "escalated"
    assert any(e["type"] == "escalated" and e["reason"] == "sensitive_topic" for e in body["events"])


def test_agent_cannot_escalate_with_system_reasons(api):
    case = profiling_case(api)
    resp = case.call("escalate", {"reason": "mismatch_persisted"})
    assert resp.status_code == 422 and resp.json()["rejection"]["code"] == "invalid_input"


@pytest.mark.req("FR-043")
def test_escalated_case_blocks_agent_business_tools_but_not_messages(api):
    case, _ = escalated_by_mismatch(api)
    blocked = submit(case, "payslip")
    assert blocked.status_code == 403 and blocked.json()["rejection"]["code"] == "forbidden"
    message = case.call("append_message", {"message_id": "m-x", "author": "client", "text": "¿hola?"})
    assert message.status_code == 200
