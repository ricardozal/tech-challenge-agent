"""Demos 1, 3 (both branches) and 4 end to end against the compose in LLM_MODE=fake (FR-052)."""

from pathlib import Path

import httpx
import pytest

from scripts.run_demo import ACTIONS_URL, play
from scripts.seed_fixtures import seed

SCENARIOS = Path(__file__).resolve().parents[2] / "fixtures" / "scenarios"


def run(name: str) -> dict:
    path = SCENARIOS / f"{name}.yaml"
    seed(path)
    return play(path, quiet=True)  # raises if the scenario's `expected` block does not hold


def events(run_result: dict) -> list[dict]:
    return [ev for entry in run_result["audit"] for ev in entry["events"]]


@pytest.mark.req("FR-052")
@pytest.mark.req("FR-036")
def test_demo_1_happy_path(compose_up):
    result = run("happy_path")
    gate = [e for e in result["audit"] if e["tool"] == "evaluate_gate"]
    assert result["case"]["status"] == "ok_for_lender"
    assert [(e["actor"], e["outcome"]) for e in gate] == [("system", "accepted")]


@pytest.mark.req("FR-052")
def test_demo_3_correction_branch(compose_up):
    result = run("document_correction")
    income = [ev for ev in events(result) if ev["type"] == "validation_recorded" and ev["key"] == "income"]
    assert [ev["result"] for ev in income] == ["mismatch", "passed"]
    assert result["case"]["status"] == "ok_for_lender"


@pytest.mark.req("FR-052")
@pytest.mark.req("FR-038")
@pytest.mark.req("FR-045")
def test_demo_3_escalation_branch_and_advisor_verification(compose_up):
    result = run("document_escalation")
    case = result["case"]
    assert case["status"] == "escalated"
    assert any(ev["type"] == "escalated" and ev["reason"] == "mismatch_persisted" for ev in events(result))

    call = {"context": {"case_id": case["id"], "idempotency_key": f"e2e-verify-{case['id']}",
                        "expected_version": case["version"]},
            "input": {"validation_key": "income", "justification": "Ingreso confirmado por llamada con el empleador",
                      "evidence": ["llamada-2026-10-04"]}}
    resp = httpx.post(f"{ACTIONS_URL}/tools/verify_validation_manually", json=call, headers={"X-Actor": "advisor"})
    assert resp.status_code == 200 and resp.json()["case"]["status"] == "ok_for_lender"


@pytest.mark.req("FR-052")
@pytest.mark.req("FR-022")
def test_demo_4_no_spare_key(compose_up):
    result = run("no_spare_key")
    state = result["case"]["state"]
    assert state["key_quote"]["amount"] == "2400.00"
    assert all(o["key_cost"] == "2400.00" for o in state["options"])
    assert state["options"][0]["client_amount"] == "97600.00"
    assert result["case"]["status"] == "ok_for_lender"
