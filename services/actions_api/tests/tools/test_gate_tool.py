"""evaluate_gate: automatic on validation changes, requestable by the agent (FR-036, FR-037, R-08)."""

import pytest

from tests.support.cases import documents_case
from tests.support.reader import LOW_PAYSLIP, install, submit

DOCS = ("identification", "payslip", "proof_of_address", "vehicle_invoice")


@pytest.mark.req("FR-036")
def test_last_passing_document_triggers_the_gate_as_a_separate_system_action(api):
    install(api)
    case = documents_case(api)
    for doc in DOCS[:-1]:
        body = submit(case, doc).json()
        assert body["case"]["status"] == "active"
        assert any(e["type"] == "gate_failed" for e in body["events"])
    last = submit(case, DOCS[-1]).json()

    assert last["case"]["status"] == "ok_for_lender"
    assert last["result"]["followups"][0]["tool"] == "evaluate_gate"
    entries = api.audit(case.id)
    gate = [e for e in entries if e["tool"] == "evaluate_gate"]
    assert len(gate) == 1 and gate[0]["actor"] == "system" and gate[0]["outcome"] == "accepted"
    assert {"type": "gate_passed"} in gate[0]["events"]
    assert gate[0]["policy_version"] == "2026.10-v1"
    assert case.view()["state"]["decisions"][-1]["kind"] == "gate"


@pytest.mark.req("FR-037")
def test_agent_request_with_pending_validations_is_rejected_and_audited(api):
    reader = install(api)
    reader.overrides["payslip"] = LOW_PAYSLIP
    case = documents_case(api)
    for doc in DOCS:
        submit(case, doc)
    version = case.version
    resp = case.call("evaluate_gate")

    assert resp.status_code == 409
    body = resp.json()
    assert body["rejection"]["code"] == "gate_not_met" and body["rejection"]["details"]["missing"] == ["income"]
    assert case.view()["status"] == "active" and case.view()["version"] == version
    entry = api.audit(case.id)[-1]
    assert entry["tool"] == "evaluate_gate" and entry["actor"] == "agent" and entry["rejection_code"] == "gate_not_met"
