"""Action layer guarantees: idempotency, expected version, audit, permissions (R-05)."""

import pytest

from actions_api.permissions import MATRIX
from actions_api.toolkit import REGISTRY
from contracts.actions import TOOL_INPUTS


@pytest.mark.req("FR-005")
def test_replaying_an_idempotency_key_returns_the_stored_response_without_rerunning(api):
    case = api.create_case()
    first = api.call("update_declared_data", case["id"], case["version"], key="same-key",
                     input={"full_name": "Laura Méndez Rojas"})
    second = api.call("update_declared_data", case["id"], case["version"], key="same-key",
                      input={"full_name": "Laura Méndez Rojas"})

    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    assert api.case(case["id"])["version"] == case["version"] + 1
    assert [e["idempotency_key"] for e in api.audit(case["id"])].count("same-key") == 1


@pytest.mark.req("FR-005")
def test_same_key_with_a_different_request_is_rejected(api):
    case = api.create_case()
    api.call("update_declared_data", case["id"], case["version"], key="k1", input={"make": "Volkswagen"})
    resp = api.call("update_declared_data", case["id"], case["version"] + 1, key="k1", input={"make": "Nissan"})

    assert resp.status_code == 409
    assert resp.json()["rejection"]["code"] == "idempotency_mismatch"
    assert api.case(case["id"])["state"]["vehicle"]["make"] == "Volkswagen"


@pytest.mark.req("FR-006")
def test_stale_expected_version_is_rejected_without_changes(api):
    case = api.create_case()
    api.call("update_declared_data", case["id"], case["version"], input={"make": "Volkswagen"})
    stale = api.call("update_declared_data", case["id"], case["version"], input={"make": "Nissan"})

    assert stale.status_code == 409
    body = stale.json()
    assert body["rejection"]["code"] == "version_conflict"
    assert body["rejection"]["details"] == {"expected_version": 1, "current_version": 2}
    current = api.case(case["id"])
    assert current["version"] == 2
    assert current["state"]["vehicle"]["make"] == "Volkswagen"


@pytest.mark.req("FR-007")
def test_accepted_and_rejected_actions_are_both_audited(api):
    case = api.create_case()
    api.call("update_declared_data", case["id"], 1, input={"own_name": True}, on_behalf_of="client",
             evidence_message_id="m-1")
    api.call("update_declared_data", case["id"], 1, input={"own_name": False})  # stale version

    entries = [e for e in api.audit(case["id"]) if e["tool"] == "update_declared_data"]
    assert [e["outcome"] for e in entries] == ["accepted", "rejected"]
    accepted, rejected = entries
    assert accepted["actor"] == "agent" and accepted["on_behalf_of"] == "client"
    assert accepted["stage_before"] == "eligibility" and accepted["status_before"] == "active"
    assert accepted["input"] == {"own_name": True, "evidence_message_id": "m-1"}
    assert accepted["case_version_after"] == 2 and accepted["policy_version"] == "2026.10-v1"
    assert rejected["rejection_code"] == "version_conflict"
    assert rejected["result"]["message"]


@pytest.mark.req("FR-004")
def test_forbidden_actor_is_rejected_without_modifying_the_case(api):
    case = api.create_case()
    resp = api.call("update_declared_data", case["id"], 1, actor="advisor", input={"make": "Nissan"})

    assert resp.status_code == 403
    assert resp.json()["rejection"]["code"] == "forbidden"
    assert api.case(case["id"])["version"] == 1
    assert api.audit(case["id"])[-1]["rejection_code"] == "forbidden"


@pytest.mark.req("FR-004")
def test_closed_case_rejects_business_tools(api):
    case = api.create_case()
    cancel = api.call("cancel_case", case["id"], 1, on_behalf_of="client", input={"reason": "ya no quiero"})
    assert cancel.json()["case"]["status"] == "cancelled"

    resp = api.call("update_declared_data", case["id"], 2, input={"make": "Nissan"})
    assert resp.status_code == 409
    assert resp.json()["rejection"]["code"] == "case_closed"


@pytest.mark.req("FR-003")
def test_every_tool_has_input_contract_and_permissions_and_reads_do_not_write(api):
    assert set(REGISTRY) <= set(TOOL_INPUTS) == set(MATRIX)

    case = api.create_case()
    before = len(api.audit(case["id"]))
    for path in (f"/cases/{case['id']}", "/cases", f"/cases/{case['id']}/audit", "/escalations"):
        assert api.client.get(path).status_code == 200
    assert len(api.audit(case["id"])) == before
    assert api.case(case["id"])["version"] == 1


@pytest.mark.req("FR-002")
def test_case_view_exposes_stage_status_data_decisions_documents_validations(api):
    case = api.create_case()
    api.call("update_declared_data", case["id"], 1, input={"full_name": "Laura Méndez Rojas", "make": "Volkswagen"},
             evidence_message_id="m-7")

    view = api.case(case["id"])
    assert view["stage"] == "eligibility" and view["status"] == "active"
    assert view["state"]["client"]["full_name"] == "Laura Méndez Rojas"
    assert view["state"]["client"]["sources"] == {"full_name": "m-7"}
    for section in ("decisions", "documents", "validations", "options", "messages"):
        assert section in view["state"]
    assert view["state"]["open_escalation_id"] is None
