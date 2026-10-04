"""Versioned policy (R-14)."""

import shutil

import psycopg
import pytest
import yaml

from actions_api.config import REPO_ROOT
from actions_api.policy import PolicyRegistry, PolicyUnavailable


@pytest.mark.req("FR-047")
def test_policy_file_holds_every_business_threshold():
    policy = PolicyRegistry.load(REPO_ROOT / "policy").current()
    assert policy.policy_version == "2026.10-v1"
    assert [b.band for b in policy.profile_bands] == ["A", "B", "C"]
    assert str(policy.vehicle.max_financeable_pct_of_value) == "0.50"
    assert [str(p) for p in policy.options.pcts_of_max] == ["1.00", "0.75", "0.50"]
    assert str(policy.income.tolerance_pct) == "0.10"
    assert str(policy.documents.min_field_confidence) == "0.80"
    assert str(policy.matching.name_similarity_threshold) == "0.90"
    assert policy.escalation.max_correction_attempts == 2
    assert policy.escalation.provider_retries == 2


@pytest.mark.req("FR-047")
def test_archived_versions_are_resolvable_and_unknown_ones_fail(tmp_path):
    shutil.copytree(REPO_ROOT / "policy", tmp_path / "policy")
    old = yaml.safe_load((tmp_path / "policy" / "policy.yaml").read_text())
    old["policy_version"] = "2026.09-v0"
    old["income"]["tolerance_pct"] = "0.05"
    (tmp_path / "policy" / "archive" / "2026.09-v0.yaml").write_text(yaml.safe_dump(old))

    registry = PolicyRegistry.load(tmp_path / "policy")
    assert registry.current().policy_version == "2026.10-v1"
    assert str(registry.get("2026.09-v0").income.tolerance_pct) == "0.05"
    with pytest.raises(PolicyUnavailable):
        registry.get("1999-v9")


@pytest.mark.req("FR-048")
def test_case_pins_the_current_policy_version_and_actions_record_it(api):
    case = api.create_case()
    api.call("update_declared_data", case["id"], 1, input={"make": "Volkswagen"})

    assert api.case(case["id"])["policy_version"] == "2026.10-v1"
    assert {e["policy_version"] for e in api.audit(case["id"])} == {"2026.10-v1"}


@pytest.mark.req("FR-048")
def test_case_whose_policy_is_not_loaded_is_rejected_and_escalated(api, test_db):
    case = api.create_case()
    with psycopg.connect(test_db.actions_url, autocommit=True) as conn:
        conn.execute("UPDATE cases.cases SET policy_version = '1999-v9' WHERE id = %s", (case["id"],))

    resp = api.call("update_declared_data", case["id"], 1, input={"make": "Volkswagen"}, key="k-missing-policy")
    again = api.call("update_declared_data", case["id"], 1, input={"make": "Volkswagen"}, key="k-missing-policy")

    assert resp.status_code == 409 and resp.json()["rejection"]["code"] == "policy_unavailable"
    assert again.json() == resp.json()  # a retry does not escalate twice
    view = api.case(case["id"])
    assert view["status"] == "escalated" and view["state"]["vehicle"]["make"] is None
    tickets = [t for t in api.client.get("/escalations").json() if t["case_id"] == case["id"]]
    assert [t["reason"] for t in tickets] == ["policy_unavailable"]
    assert tickets[0]["evidence"]["policy_version"] == "1999-v9"
    escalate = [e for e in api.audit(case["id"]) if e["tool"] == "escalate"]
    assert [(e["actor"], e["outcome"]) for e in escalate] == [("system", "accepted")]
