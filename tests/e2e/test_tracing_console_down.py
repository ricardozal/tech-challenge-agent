"""Turns never depend on the trace console (FR-092, SC-022)."""

import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.run_demo import play

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "fixtures" / "scenarios").glob("*.yaml"))


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, capture_output=True)


@pytest.mark.req("FR-092")
def test_demos_finish_the_same_with_phoenix_stopped(compose_up):
    compose("stop", "phoenix")
    try:
        for scenario in SCENARIOS:
            expected = yaml.safe_load(scenario.read_text(encoding="utf-8")).get("expected", {})
            result = play(scenario, quiet=True)  # raises DemoFailure if the outcome differs
            if "status" in expected:
                assert result["case"]["status"] == expected["status"], scenario.stem
    finally:
        compose("start", "phoenix")
