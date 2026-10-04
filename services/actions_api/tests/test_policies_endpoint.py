"""GET /policies/{policy_version}: read-only policy for the advisor console (specs/002-demo-web W-11)."""

import pytest

from actions_api.config import REPO_ROOT
from actions_api.policy import PolicyRegistry

CURRENT = PolicyRegistry.load(REPO_ROOT / "policy").current().policy_version


@pytest.mark.req("FR-066")
def test_returns_the_policy_of_that_version(client):
    audit_before = client.get("/metrics").json()["audit_entries"]

    resp = client.get(f"/policies/{CURRENT}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_version"] == CURRENT
    assert body["documents"]["min_field_confidence"] == "0.80"
    assert client.get("/metrics").json()["audit_entries"] == audit_before  # a read, not an action


def test_unknown_version_is_404(client):
    resp = client.get("/policies/does-not-exist")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "policy not found"}
