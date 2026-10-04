"""Profiling and simulation tools: consent, bureau, profile, options, selection (P2)."""

import pytest

from tests.support.cases import consented, profiling_case


@pytest.mark.req("FR-018")
def test_credit_check_without_consent_is_rejected_and_the_bureau_is_not_called(api):
    calls = []
    api.client.app.state.services.extras["bureau"].score = lambda *a: calls.append(a)
    c = profiling_case(api)
    resp = c.call("run_credit_check")
    assert resp.status_code == 422 and resp.json()["rejection"]["code"] == "consent_required"
    assert calls == []


@pytest.mark.req("FR-004")
def test_consent_needs_the_client_message_as_evidence_and_is_audited_on_their_behalf(api):
    c = profiling_case(api)
    without = c.call("record_bureau_consent", {"consent": True}, on_behalf_of="client")
    assert without.status_code == 422 and without.json()["rejection"]["code"] == "invalid_input"

    c.call("record_bureau_consent", {"consent": True}, on_behalf_of="client", evidence_message_id="m-9")
    entry = [e for e in api.audit(c.id) if e["tool"] == "record_bureau_consent"][-1]
    assert entry["outcome"] == "accepted" and entry["on_behalf_of"] == "client"
    assert entry["input"]["evidence_message_id"] == "m-9"
    assert c.view()["state"]["declared"]["bureau_consent_message_id"] == "m-9"


@pytest.mark.req("FR-019")
@pytest.mark.req("FR-048")
def test_credit_check_assigns_the_profile_with_policy_version(api):
    c = consented(api)
    body = c.call("run_credit_check").json()
    assert body["case"]["stage"] == "simulation"
    assert {"type": "profile_assigned", "band": "A"} in body["events"]
    profile = c.view()["state"]["profile"]
    assert profile["bureau_score"] == 720 and profile["max_financeable"] == "90000.00"
    assert profile["policy_version"] == "2026.10-v1"


@pytest.mark.req("FR-021")
@pytest.mark.req("FR-048")
def test_options_are_simulated_and_carry_the_policy_version(api):
    c = consented(api)
    c.call("run_credit_check")
    body = c.call("simulate_options").json()
    options = body["result"]["options"]
    assert [o["id"] for o in options] == ["opt-100", "opt-75", "opt-50"]
    assert options[0]["monthly_payment"] == "4932.63"
    assert {o["policy_version"] for o in c.view()["state"]["options"]} == {"2026.10-v1"}


@pytest.mark.req("FR-022")
def test_options_include_the_quoted_key(api):
    c = consented(api, spare_key=False)
    c.call("run_credit_check")
    first = c.call("simulate_options").json()["result"]["options"][0]
    assert first["key_cost"] == "1850.00" and first["client_amount"] == "88150.00"


@pytest.mark.req("FR-024")
def test_selecting_a_proposed_option_moves_to_documents_and_others_are_rejected(api):
    c = consented(api)
    c.call("run_credit_check")
    c.call("simulate_options")

    bad = c.call("select_option", {"option_id": "opt-300k"}, on_behalf_of="client", evidence_message_id="m-1")
    assert bad.status_code == 422 and bad.json()["rejection"]["code"] == "invalid_input"

    ok = c.call("select_option", {"option_id": "opt-75"}, on_behalf_of="client", evidence_message_id="m-2")
    assert ok.json()["case"]["stage"] == "documents"
    assert c.view()["state"]["selected_option_id"] == "opt-75"


@pytest.mark.req("FR-020")
def test_low_score_is_rejected_without_offer(api):
    c = consented(api, full_name="Prueba Sin Oferta")
    body = c.call("run_credit_check").json()
    assert body["case"]["status"] == "rejected"
    assert {"type": "case_rejected", "reason": "no_offer_for_profile"} in body["events"]


@pytest.mark.req("FR-041")
def test_bureau_failure_escalates(api):
    c = consented(api, full_name="Prueba Falla Buro")
    body = c.call("run_credit_check").json()
    assert body["case"]["status"] == "escalated"
    assert any(e["type"] == "escalated" and e["reason"] == "provider_failure" for e in body["events"])


@pytest.mark.req("FR-020")
def test_unemployed_client_is_rejected_without_consent_or_bureau_query(api):
    calls = []
    api.client.app.state.services.extras["bureau"].score = lambda *a: calls.append(a)
    case = profiling_case(api)
    case.call("update_declared_data", {"employment": "unemployed"}, on_behalf_of="client")
    body = case.call("run_credit_check").json()

    assert body["case"]["status"] == "rejected"
    assert {"type": "case_rejected", "reason": "no_offer_for_profile"} in body["events"]
    assert calls == [] and case.view()["state"]["declared"]["bureau_consent"] is False
