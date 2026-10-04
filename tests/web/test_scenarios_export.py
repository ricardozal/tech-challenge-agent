"""web/public/scenarios.json is generated from the 001 scripts and stays in sync (W-05, W-06)."""

import json
from pathlib import Path

import pytest
import yaml

from agent.questions import DOCUMENT_QUESTIONS
from contracts.common import DocumentType
from scripts.export_web_scenarios import OUTPUT, build

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "fixtures" / "scenarios"
EXPORT = build()
SCENARIOS = {s["id"]: s for s in EXPORT["scenarios"]}


def _say_steps(script: str) -> list[dict]:
    steps = yaml.safe_load((SCRIPTS / f"{script}.yaml").read_text(encoding="utf-8"))["steps"]
    return [{"stage": s.get("stage"), "question": s.get("question"), "text": s["say"]} for s in steps if "say" in s]


@pytest.mark.req("FR-056")
@pytest.mark.req("FR-057")
def test_committed_file_is_up_to_date():
    committed = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert committed == EXPORT, "run `make web-scenarios` and commit web/public/scenarios.json"


@pytest.mark.req("FR-056")
def test_the_four_scenarios_of_the_web():
    assert list(SCENARIOS) == ["happy_path", "eligibility_rejection", "document_failed", "no_spare_key"]
    for scenario in SCENARIOS.values():
        assert scenario["title"] and scenario["description"] and scenario["client_name"]


@pytest.mark.req("FR-057")
def test_messages_come_from_the_scripts_with_their_question():
    for scenario in SCENARIOS.values():
        allowed = [step for script in scenario["source_scripts"] for step in _say_steps(script)]
        assert scenario["messages"], scenario["id"]
        for message in scenario["messages"]:
            assert message in allowed, (scenario["id"], message)


def test_document_questions_are_the_agent_questions():
    for scenario in SCENARIOS.values():
        for slot in scenario["documents"]:
            key = slot["slot"] if slot["slot"] == "income_proof" else DocumentType(slot["slot"])
            assert slot["question"] == DOCUMENT_QUESTIONS[key].text, (scenario["id"], slot["slot"])


def test_sample_documents_exist_and_have_valid_types():
    for scenario in SCENARIOS.values():
        for slot in scenario["documents"]:
            for option in slot["options"]:
                assert (ROOT / "fixtures" / option["file"]).is_file(), option["file"]
                DocumentType(option["requested_type"])


@pytest.mark.req("FR-060")
def test_only_document_failed_offers_two_income_proofs():
    for scenario in SCENARIOS.values():
        multi = [slot for slot in scenario["documents"] if len(slot["options"]) > 1]
        if scenario["id"] == "document_failed":
            assert [slot["slot"] for slot in multi] == ["income_proof"]
            assert sorted(o["variant"] for o in multi[0]["options"]) == ["mismatch", "ok"]
        else:
            assert multi == [], scenario["id"]
