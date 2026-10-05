"""One trace per agent turn in the local Phoenix console (FR-085…FR-089, FR-093, SC-020; contracts/tracing.md)."""

import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
import yaml

from scripts.run_demo import play
from tests.conftest import AGENT_URL

PHOENIX_URL = "http://localhost:6006"
PROJECT = "tech-challenge-agent"
ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "fixtures" / "scenarios").glob("*.yaml"))


@pytest.fixture(scope="module")
def phoenix(compose_up):
    try:
        httpx.get(f"{PHOENIX_URL}/healthz", timeout=3).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("phoenix is not running on :6006")
    from phoenix.client import Client

    return Client(base_url=PHOENIX_URL)


def turns_of(phoenix, case_id: str, expected: int) -> list[dict]:
    """`turn` spans of a case. Export is batched and Phoenix ingests asynchronously; after a burst of
    tests it can lag (≈1 min measured after the e2e suite), so wait up to 180 s."""
    deadline = time.monotonic() + 180
    while True:
        turns = phoenix.spans.get_spans(project_identifier=PROJECT, name="turn",
                                        attributes={"session.id": case_id}, limit=500)
        if len(turns) >= expected or time.monotonic() > deadline:
            return sorted(turns, key=lambda s: s["start_time"])
        time.sleep(0.5)


def spans_of(phoenix, trace_id: str) -> list[dict]:
    deadline = time.monotonic() + 180
    previous = -1
    while True:
        spans = phoenix.spans.get_spans(project_identifier=PROJECT, trace_ids=[trace_id], limit=1000)
        if len(spans) == previous or time.monotonic() > deadline:
            return sorted(spans, key=lambda s: s["start_time"])
        previous = len(spans)
        time.sleep(1)


def agent_turns(scenario: Path) -> int:
    steps = yaml.safe_load(scenario.read_text(encoding="utf-8")).get("steps", [])
    return 1 + sum(1 for s in steps if "say" in s or "upload" in s)  # greeting + client turns


@pytest.mark.req("FR-085")
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda p: p.stem)
def test_every_turn_is_exactly_one_trace(phoenix, scenario):
    case_id = str(play(scenario, quiet=True)["case"]["id"])
    turns = turns_of(phoenix, case_id, agent_turns(scenario))
    assert len(turns) == agent_turns(scenario)
    assert len({t["context"]["trace_id"] for t in turns}) == len(turns)
    assert all(t["parent_id"] is None for t in turns)  # the turn is the root of its trace


@pytest.fixture(scope="module")
def happy_path(phoenix):
    scenario = ROOT / "fixtures" / "scenarios" / "happy_path.yaml"
    case_id = str(play(scenario, quiet=True)["case"]["id"])
    turns = turns_of(phoenix, case_id, agent_turns(scenario))
    return case_id, turns, {t["context"]["trace_id"]: spans_of(phoenix, t["context"]["trace_id"]) for t in turns}


@pytest.mark.req("FR-086")
def test_turn_identifies_case_message_and_kind(happy_path):
    case_id, turns, _ = happy_path
    for turn in turns:
        attrs = turn["attributes"]
        assert attrs["session.id"] == case_id and attrs["metadata.case_id"] == case_id
        assert attrs["metadata.message_id"] and attrs["metadata.kind"] in ("start", "message", "document")
        assert attrs["metadata.stage_after"] and attrs["metadata.status_after"]


@pytest.mark.req("FR-087")
def test_message_trace_shows_the_graph_stages_in_order(happy_path):
    _, turns, traces = happy_path
    for turn in (t for t in turns if t["attributes"]["metadata.kind"] == "message"):
        nodes = [s["name"] for s in traces[turn["context"]["trace_id"]] if s["span_kind"] == "CHAIN"
                 and (s["name"] in ("interpret", "respond") or s["name"].startswith(("stage_", "intent_")))]
        assert nodes[0] == "interpret" and nodes[-1] == "respond"


@pytest.mark.req("FR-088")
def test_tool_spans_have_name_input_and_outcome(happy_path):
    _, _, traces = happy_path
    tools = [s for spans in traces.values() for s in spans if s["span_kind"] == "TOOL"]
    assert {"append_message", "update_declared_data", "evaluate_eligibility"} <= {s["attributes"]["tool.name"]
                                                                                  for s in tools}
    for span in tools:
        assert "input.value" in span["attributes"]
        assert json.loads(span["attributes"]["output.value"])["outcome"] in ("accepted", "rejected")


@pytest.mark.req("FR-085")
@pytest.mark.req("FR-089")
def test_document_turn_reads_the_document_inside_the_same_trace(happy_path):
    _, turns, traces = happy_path
    doc = next(t for t in turns if t["attributes"]["metadata.kind"] == "document")
    spans = traces[doc["context"]["trace_id"]]
    names = [s["name"] for s in spans]
    assert "submit_document" in names and "read_document" in names
    models = {s["attributes"]["llm.model_name"] for s in spans if s["span_kind"] == "LLM"}
    assert {"glm-ocr", "gemma4:12b"} <= models
    assert {s["context"]["trace_id"] for s in spans} == {doc["context"]["trace_id"]}


@pytest.mark.req("FR-089")
def test_llm_spans_show_model_input_output_and_recorded_tokens(happy_path):
    _, _, traces = happy_path
    llm = [s for spans in traces.values() for s in spans if s["span_kind"] == "LLM"]
    assert llm
    for span in llm:
        attrs = span["attributes"]
        assert attrs["llm.model_name"] and "input.value" in attrs
        assert attrs["metadata.replay"] is True and attrs["metadata.fixture_origin"] in ("recorded", "seeded", "missing")
        if attrs["metadata.fixture_origin"] == "recorded":
            assert attrs["llm.token_count.prompt"] > 0 and attrs["metadata.recorded_latency_ms"] > 0


@pytest.mark.req("FR-093")
def test_no_span_input_contains_the_clients_curp(happy_path):
    _, _, traces = happy_path
    curps = set(re.findall(r"curp: (\w{18})", (ROOT / "fixtures" / "documents" / "specs.yaml").read_text(encoding="utf-8")))
    assert curps
    for spans in traces.values():
        for span in spans:
            text = " ".join(str(v) for k, v in span["attributes"].items() if k.startswith(("input.", "output.", "llm.")))
            assert not any(curp in text for curp in curps), span["name"]


@pytest.mark.req("FR-085")
def test_simultaneous_turns_of_two_cases_have_separate_traces(phoenix):
    """Edge case "Varios turnos simultáneos": no span crosses into the other case's trace."""
    with httpx.Client(timeout=60) as http:
        cases = [http.post(f"{AGENT_URL}/cases", headers={"Idempotency-Key": f"par-{uuid.uuid4()}"}).json()["case_id"]
                 for _ in range(2)]

        def send(case_id: str) -> None:
            for text in ("Hola, soy Laura Méndez Rojas", "Tengo un Volkswagen Jetta 2019"):
                http.post(f"{AGENT_URL}/cases/{case_id}/messages", json={"text": text},
                          headers={"Idempotency-Key": f"par-{uuid.uuid4()}"}).raise_for_status()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(send, cases))

    traces = {case_id: {t["context"]["trace_id"] for t in turns_of(phoenix, case_id, 3)} for case_id in cases}
    assert all(len(ids) == 3 for ids in traces.values())
    assert not traces[cases[0]] & traces[cases[1]]
    for case_id, trace_ids in traces.items():
        for trace_id in trace_ids:
            sessions = {s["attributes"].get("session.id") for s in spans_of(phoenix, trace_id)} - {None}
            assert sessions == {case_id}
