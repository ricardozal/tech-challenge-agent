"""SC-008: every number of GET /metrics matches a manual count over the action log of every case."""

from collections import Counter
from pathlib import Path

import httpx
import pytest

from scripts.run_demo import ACTIONS_URL, play
from scripts.seed_fixtures import seed

SCENARIOS = Path(__file__).resolve().parents[2] / "fixtures" / "scenarios"


@pytest.mark.req("FR-049")
def test_metrics_match_a_manual_count_of_the_audit_log(compose_up):
    for name in ("eligibility_rejection", "document_escalation", "no_spare_key"):
        seed(SCENARIOS / f"{name}.yaml")
        play(SCENARIOS / f"{name}.yaml", quiet=True)

    with httpx.Client(base_url=ACTIONS_URL, timeout=60) as http:
        report = http.get("/metrics").json()
        rejections, revoked, mismatches, key_cases, entries = Counter(), Counter(), Counter(), set(), 0
        for case in http.get("/cases").json():
            audit = http.get(f"/cases/{case['id']}/audit").json()
            entries += len(audit)
            for event in (ev for entry in audit for ev in entry["events"]):
                if event["type"] == "vehicle_rejected":
                    rejections[event["reason"]] += 1
                elif event["type"] == "ok_revoked":
                    revoked[event["reason"]] += 1
                elif event["type"] == "validation_recorded" and event["result"] != "passed":
                    mismatches[event["validation_type"]] += 1
                elif event["type"] == "key_quoted":
                    key_cases.add(case["id"])
        again = http.get("/metrics").json()

    assert report == again
    assert report["vehicle_rejections_by_reason"] == dict(rejections)
    assert report["false_ok_by_reason"] == dict(revoked)
    assert report["mismatches_by_type"] == dict(mismatches)
    assert report["cases_with_key_quote"] == len(key_cases)
    assert report["audit_entries"] >= entries  # entries without a case (e.g. rejected create calls) only add
    assert report["vehicle_rejections_by_reason"]["owner_mismatch"] >= 1 and report["cases_with_key_quote"] >= 1
