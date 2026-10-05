"""Model-call spans of the gateway (contracts/tracing.md, O-07). The exporter is OpenTelemetry's
in-memory one; the service under test is real."""

import base64
import json

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from contracts.llm import ExtractRequest, OcrRequest, fixture_key
from llm_gateway.config import REPO_ROOT
from llm_gateway.modes import LlmService, extract_inputs
from llm_gateway.schemas import Schemas

SCHEMAS = Schemas(REPO_ROOT / "eval" / "esquemas.json")
REQ = ExtractRequest(schema_name="mensaje", stage="eligibility", agent_question="¿Me compartes tu nombre completo?",
                     text="Soy Laura Méndez Rojas, CURP MERL880412MMCNJR09, tel 55 1234 5678")
ANSWER = json.dumps(SCHEMAS.complete("mensaje", {"intencion": "proporcionar_datos",
                                                 "campos": {"nombre_completo": "Laura Méndez Rojas"}}, "eligibility"))


@pytest.fixture
def exporter():
    return InMemorySpanExporter()


def service(tmp_path, mode, exporter, stub=None) -> LlmService:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    def no_ollama():
        raise AssertionError("fake mode must not create an Ollama client")

    return LlmService(mode, tmp_path, SCHEMAS, (lambda: stub) if stub else no_ollama, model="gemma4:12b",
                      ocr_model="glm-ocr", tracer=provider.get_tracer("test"))


def by_kind(exporter, kind):
    return [s for s in exporter.get_finished_spans() if s.attributes.get("openinference.span.kind") == kind]


def metadata(span) -> dict:
    return json.loads(span.attributes["metadata"])


@pytest.mark.req("FR-089")
def test_extraction_span_and_llm_span_carry_model_io_and_tokens(tmp_path, exporter, stub_ollama):
    stub_ollama.queue(ANSWER)
    service(tmp_path, "record", exporter, stub_ollama).extract(REQ)

    (task,) = by_kind(exporter, "CHAIN")
    assert task.name == "extract"
    meta = metadata(task)
    assert (meta["task"], meta["mode"], meta["schema_name"], meta["stage"], meta["schema_version"]) == (
        "extract", "record", "mensaje", "eligibility", 4)
    assert meta["fixture_key"] == fixture_key("extract", "mensaje", extract_inputs(REQ), 4)

    (llm,) = by_kind(exporter, "LLM")
    assert llm.parent.span_id == task.context.span_id
    attrs = llm.attributes
    assert attrs["llm.provider"] == "ollama" and attrs["llm.model_name"] == "gemma4:12b"
    params = json.loads(attrs["llm.invocation_parameters"])
    assert params["temperature"] == 0 and params["seed"] == 42
    assert attrs["input.value"] and attrs["output.value"]
    assert (attrs["llm.token_count.prompt"], attrs["llm.token_count.completion"], attrs["llm.token_count.total"]) == (
        812, 64, 876)
    assert metadata(llm)["attempt"] == 1


@pytest.mark.req("FR-090")
def test_each_attempt_is_its_own_llm_span_and_the_invalid_one_is_an_error(tmp_path, exporter, stub_ollama):
    stub_ollama.queue("{not json", ANSWER)
    service(tmp_path, "ollama", exporter, stub_ollama).extract(REQ)

    first, second = sorted(by_kind(exporter, "LLM"), key=lambda s: s.start_time)
    assert first.status.status_code == StatusCode.ERROR and "invalid JSON" in first.status.description
    assert second.status.status_code != StatusCode.ERROR
    assert [metadata(s)["attempt"] for s in (first, second)] == [1, 2]


@pytest.mark.req("FR-090")
def test_task_span_is_an_error_when_both_attempts_fail(tmp_path, exporter, stub_ollama):
    stub_ollama.queue("{not json", "{still not json")
    with pytest.raises(Exception):
        service(tmp_path, "ollama", exporter, stub_ollama).extract(REQ)
    (task,) = by_kind(exporter, "CHAIN")
    assert task.status.status_code == StatusCode.ERROR


@pytest.mark.req("FR-089")
def test_replay_shows_origin_and_the_recorded_latency_and_tokens(tmp_path, exporter):
    key = fixture_key("extract", "mensaje", extract_inputs(REQ), 4)
    (tmp_path / "extract").mkdir()
    (tmp_path / "extract" / f"{key}.json").write_text(json.dumps({
        "request": {}, "response": json.loads(ANSWER), "origin": "recorded", "latency_ms": 6123.4,
        "prompt_tokens": 700, "completion_tokens": 40}))
    service(tmp_path, "fake", exporter).extract(REQ)

    (llm,) = by_kind(exporter, "LLM")
    meta = metadata(llm)
    assert meta["replay"] is True and meta["fixture_origin"] == "recorded" and meta["recorded_latency_ms"] == 6123.4
    assert (llm.attributes["llm.token_count.prompt"], llm.attributes["llm.token_count.completion"]) == (700, 40)


def test_missing_replay_is_marked_missing(tmp_path, exporter):
    service(tmp_path, "fake", exporter).extract(REQ)
    (llm,) = by_kind(exporter, "LLM")
    assert metadata(llm)["fixture_origin"] == "missing"


def test_ocr_span_never_carries_the_image(tmp_path, exporter, stub_ollama):
    content = b"\x89PNG fake image bytes"
    service(tmp_path, "ollama", exporter, stub_ollama).ocr(OcrRequest(content_base64=base64.b64encode(content).decode()))
    encoded = base64.b64encode(content).decode()
    for span in exporter.get_finished_spans():
        assert all(encoded not in str(v) for v in span.attributes.values())
    (task,) = by_kind(exporter, "CHAIN")
    assert "sha256" in task.attributes["input.value"]
    (llm,) = by_kind(exporter, "LLM")
    assert llm.attributes["llm.model_name"] == "glm-ocr"


@pytest.mark.req("FR-093")
def test_inputs_and_outputs_are_redacted(tmp_path, exporter, stub_ollama):
    stub_ollama.queue(ANSWER)
    service(tmp_path, "ollama", exporter, stub_ollama).extract(REQ)
    for span in exporter.get_finished_spans():
        text = " ".join(str(v) for k, v in span.attributes.items() if k.startswith(("input.", "output.", "llm.input",
                                                                                     "llm.output")))
        assert "MERL880412MMCNJR09" not in text and "1234 5678" not in text and "Laura" not in text
    (llm,) = by_kind(exporter, "LLM")
    assert "[REDACTED_CURP]" in llm.attributes["input.value"]
    assert "[REDACTED_PHONE]" in llm.attributes["input.value"]
    assert "[REDACTED_NAME]" in llm.attributes["output.value"]
