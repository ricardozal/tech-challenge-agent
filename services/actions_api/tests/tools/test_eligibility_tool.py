"""evaluate_eligibility tool with the simulated vehicle registry and key quote (P1, R-15).

Uses fixtures/providers: special names trigger a lien, a provider failure or a missing value.
"""

import pytest

CLEAN = {"full_name": "Laura Méndez Rojas", "make": "Volkswagen", "model": "Jetta", "year": 2019,
         "own_name": True, "declared_debt": False, "spare_key": True}


def declared_case(api, **overrides):
    case = api.create_case()
    data = {**CLEAN, **overrides}
    resp = api.call("update_declared_data", case["id"], 1, input=data, on_behalf_of="client")
    assert resp.status_code == 200, resp.text
    return case["id"], 2


def evaluate(api, case_id, version):
    return api.call("evaluate_eligibility", case_id, version)


@pytest.mark.req("FR-011")
def test_registry_is_queried_with_declared_name_and_vehicle(api):
    calls = []
    registry = api.client.app.state.services.extras["vehicle_registry"]
    original = registry.lookup
    registry.lookup = lambda *args: calls.append(args) or original(*args)

    case_id, version = declared_case(api)
    resp = evaluate(api, case_id, version)

    assert resp.status_code == 200, resp.text
    assert calls == [("Laura Méndez Rojas", "Volkswagen", "Jetta", 2019)]
    view = api.case(case_id)
    assert view["stage"] == "profiling" and view["status"] == "active"
    assert view["state"]["vehicle"]["registry"]["reference_value"] == "180000"
    assert view["state"]["key_quote"] is None


@pytest.mark.req("FR-014")
@pytest.mark.req("FR-048")
def test_missing_spare_key_is_quoted_and_recorded_with_policy_version(api):
    case_id, version = declared_case(api, spare_key=False)
    resp = evaluate(api, case_id, version)

    body = resp.json()
    assert body["case"]["stage"] == "profiling"
    assert {"type": "key_quoted", "amount": "1850.00", "quote_id": "KQ-VW-JETTA-2019"} in body["events"]
    quote = api.case(case_id)["state"]["key_quote"]
    assert quote["amount"] == "1850.00" and quote["policy_version"] == "2026.10-v1"
    decision = api.case(case_id)["state"]["decisions"][-1]
    assert decision["kind"] == "eligibility" and decision["result"] == "eligible"
    assert decision["policy_version"] == "2026.10-v1"


@pytest.mark.req("FR-012")
def test_owner_mismatch_rejects_without_querying_the_registry(api):
    calls = []
    registry = api.client.app.state.services.extras["vehicle_registry"]
    registry.lookup = lambda *args: calls.append(args)

    case_id, version = declared_case(api, own_name=False, declared_debt=None, spare_key=None)
    body = evaluate(api, case_id, version).json()

    assert body["case"]["status"] == "rejected"
    assert {"type": "vehicle_rejected", "reason": "owner_mismatch", "origin": "declared"} in body["events"]
    assert calls == []


@pytest.mark.req("FR-013")
def test_registry_lien_rejects_with_registry_origin(api):
    case_id, version = declared_case(api, full_name="Sofía Castillo Pérez", make="Mazda", model="3", year=2020)
    body = evaluate(api, case_id, version).json()

    assert body["case"]["status"] == "rejected"
    assert {"type": "vehicle_rejected", "reason": "lien_or_debt", "origin": "registry"} in body["events"]


@pytest.mark.req("FR-041")
def test_registry_failure_after_retries_escalates(api):
    calls = []
    registry = api.client.app.state.services.extras["vehicle_registry"]
    original = registry.lookup
    registry.lookup = lambda *args: calls.append(args) or original(*args)

    case_id, version = declared_case(api, full_name="Prueba Falla Proveedor")
    body = evaluate(api, case_id, version).json()

    assert len(calls) == 3  # first attempt + provider_retries = 2
    assert body["outcome"] == "accepted"
    assert body["case"]["status"] == "escalated"
    assert any(e["type"] == "escalated" and e["reason"] == "provider_failure" for e in body["events"])
    escalated = next(e for e in body["events"] if e["type"] == "escalated")
    assert escalated["by"] == "system"  # automatic escalation: its own action by the system (R-09)
    escalation = api.client.get(f"/escalations/{escalated['escalation_id']}").json()
    assert escalation["status"] == "open" and escalation["reason"] == "provider_failure"
    assert escalation["summary"] and escalation["suggested_action"]
    tools = [(e["tool"], e["actor"]) for e in api.audit(case_id)][-2:]
    assert tools == [("evaluate_eligibility", "agent"), ("escalate", "system")]


def test_missing_reference_value_escalates(api):
    case_id, version = declared_case(api, full_name="Prueba Sin Valor", make="Chevrolet", model="Aveo", year=2010)
    body = evaluate(api, case_id, version).json()
    assert body["case"]["status"] == "escalated"
    assert any(e["type"] == "escalated" and e["reason"] == "no_reference_value" for e in body["events"])


@pytest.mark.req("FR-015")
def test_incomplete_declaration_is_not_decided(api):
    case_id, version = declared_case(api, spare_key=None)
    resp = evaluate(api, case_id, version)
    assert resp.status_code == 422
    assert resp.json()["rejection"]["code"] == "unconfirmed_data"
    assert resp.json()["rejection"]["details"]["missing"] == ["spare_key"]
    assert api.case(case_id)["state"]["decisions"] == []


@pytest.mark.req("FR-016")
def test_rejected_case_accepts_no_more_business_actions(api):
    case_id, version = declared_case(api, own_name=False)
    evaluate(api, case_id, version)
    resp = api.call("update_declared_data", case_id, version + 1, input={"own_name": True})
    assert resp.status_code == 409 and resp.json()["rejection"]["code"] == "case_closed"
