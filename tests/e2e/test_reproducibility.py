"""SC-001 and SC-002: the five scripts give identical results 10 times in a row, each under 2 minutes,
with no GPU and recorded LLM answers (FR-051)."""

from pathlib import Path

import pytest

from scripts.run_demo import play
from scripts.seed_fixtures import seed

SCENARIOS = sorted((Path(__file__).resolve().parents[2] / "fixtures" / "scenarios").glob("*.yaml"))
RUNS = 10


def signature(result: dict) -> tuple:
    """What must not change between runs: final state and the sequence of actions and outcomes."""
    case = result["case"]
    actions = tuple(
        (e["actor"], e["tool"], e["outcome"], e["rejection_code"], tuple(ev["type"] for ev in e["events"]))
        for e in result["audit"]
    )
    return case["stage"], case["status"], case["version"], actions


@pytest.mark.req("FR-051")
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda p: p.stem)
def test_scenario_is_reproducible_and_fast(compose_up, scenario):
    seed(scenario)
    runs = [play(scenario, quiet=True) for _ in range(RUNS)]
    assert len({signature(r) for r in runs}) == 1
    assert max(r["elapsed_s"] for r in runs) < 120
