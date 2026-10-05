"""Fixture key with schema and prompt versions (O-10)."""

import pytest

from contracts import llm
from contracts.llm import fixture_key

INPUTS = {"stage": "eligibility", "agent_question": "¿El auto está a tu nombre?", "text": "Sí, está a mi nombre"}


@pytest.mark.req("FR-083")
def test_key_changes_with_the_schema_version():
    assert fixture_key("extract", "mensaje", INPUTS, schema_version=4) != fixture_key(
        "extract", "mensaje", INPUTS, schema_version=3
    )


@pytest.mark.req("FR-083")
def test_key_changes_with_the_prompt_version(monkeypatch):
    before = fixture_key("extract", "mensaje", INPUTS, schema_version=4)
    monkeypatch.setattr(llm, "PROMPT_VERSION", llm.PROMPT_VERSION + 1)
    assert fixture_key("extract", "mensaje", INPUTS, schema_version=4) != before


def test_key_ignores_case_and_repeated_spaces():
    noisy = {**INPUTS, "text": "  SÍ,   está a mi   NOMBRE "}
    assert fixture_key("extract", "mensaje", noisy, schema_version=4) == fixture_key(
        "extract", "mensaje", INPUTS, schema_version=4
    )
