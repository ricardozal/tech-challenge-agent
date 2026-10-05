"""The 4 demos replay only authentic recorded answers in LLM_MODE=fake (FR-082, FR-083, SC-019)."""

import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from scripts.run_demo import play
from tests.conftest import LLM_URL

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "fixtures" / "scenarios").glob("*.yaml"))


@pytest.fixture
def fake_gateway(compose_up):
    if httpx.get(f"{LLM_URL}/health", timeout=5).json().get("mode") != "fake":
        pytest.skip("the gateway is not in LLM_MODE=fake")


@pytest.mark.req("FR-082")
@pytest.mark.req("FR-083")
def test_demos_use_only_recorded_answers(fake_gateway):
    httpx.delete(f"{LLM_URL}/v1/fixtures/usage", timeout=5).raise_for_status()
    for scenario in SCENARIOS:
        play(scenario, quiet=True)
    counts = httpx.get(f"{LLM_URL}/v1/fixtures/usage", timeout=5).json()["counts"]
    assert counts["seeded"] == 0, counts
    assert counts["missing"] == 0, counts
    assert counts["recorded"] > 0


@pytest.mark.req("FR-083")
def test_fixtures_status_command_reports_no_seeded_or_missing(fake_gateway):
    result = subprocess.run([sys.executable, "scripts/fixtures_status.py"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "auténticas" in result.stdout
