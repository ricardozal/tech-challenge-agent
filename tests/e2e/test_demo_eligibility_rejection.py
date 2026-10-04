"""Demo 2 · rechazo por elegibilidad, end to end against the compose (LLM_MODE=fake)."""

from pathlib import Path

import pytest

from scripts.run_demo import play
from scripts.seed_fixtures import seed

SCENARIO = Path(__file__).resolve().parents[2] / "fixtures" / "scenarios" / "eligibility_rejection.yaml"


@pytest.mark.req("FR-012")
@pytest.mark.req("FR-052")
def test_demo_eligibility_rejection(compose_up):
    seed(SCENARIO)
    run = play(SCENARIO, quiet=True)  # raises if the scenario's `expected` block does not hold

    assert run["case"]["status"] == "rejected"
    rejection = next(e for e in run["audit"] if e["tool"] == "evaluate_eligibility")
    assert {"type": "vehicle_rejected", "reason": "owner_mismatch", "origin": "declared"} in rejection["events"]
    assert "run_credit_check" not in run["tools"]
