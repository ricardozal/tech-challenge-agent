"""LLM_MODE=record writes fixture v2 to the recording directory, never to fixtures/llm (O-10, O-11)."""

import base64
import json

import pytest

from contracts.llm import PROMPT_VERSION, ExtractRequest, OcrRequest, ReplyRequest
from llm_gateway.config import REPO_ROOT
from llm_gateway.modes import InvalidModelOutput, LlmService
from llm_gateway.schemas import Schemas

SCHEMAS = Schemas(REPO_ROOT / "eval" / "esquemas.json")
REQ = ExtractRequest(schema_name="mensaje", stage="eligibility", agent_question="¿El auto está a tu nombre?",
                     text="sí, está a mi nombre")


def service(tmp_path, mode, stub) -> LlmService:
    return LlmService(mode, tmp_path / "llm", SCHEMAS, lambda: stub, model="gemma4:12b", ocr_model="glm-ocr",
                      record_dir=tmp_path / "llm" / "_recording")


def files(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*.json")) if root.exists() else []


@pytest.mark.req("FR-080")
def test_record_writes_every_task_to_the_recording_dir_only(tmp_path, stub_ollama):
    svc = service(tmp_path, "record", stub_ollama)
    svc.extract(REQ)
    svc.ocr(OcrRequest(content_base64=base64.b64encode(b"png").decode()))
    svc.reply(ReplyRequest(stage="eligibility", status="active", next_question="¿Qué auto es?"))

    recorded = files(tmp_path / "llm" / "_recording")
    assert [p.split("/")[0] for p in recorded] == ["extract", "ocr", "reply"]
    assert [p for p in files(tmp_path / "llm") if not p.startswith("_recording/")] == []


@pytest.mark.req("FR-080")
def test_recorded_fixture_has_origin_versions_latency_and_tokens(tmp_path, stub_ollama):
    service(tmp_path, "record", stub_ollama).extract(REQ)
    (path,) = (tmp_path / "llm" / "_recording" / "extract").glob("*.json")
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["origin"] == "recorded"
    assert record["model"] == "gemma4:12b" and record["recorded_at"]
    assert record["schema_version"] == 4 and record["prompt_version"] == PROMPT_VERSION
    assert isinstance(record["latency_ms"], int | float)
    assert (record["prompt_tokens"], record["completion_tokens"]) == (812, 64)


@pytest.mark.req("FR-080")
def test_metrics_are_those_of_the_valid_attempt(tmp_path, stub_ollama):
    valid = json.dumps(SCHEMAS.complete("mensaje", {"intencion": "proporcionar_datos",
                                                    "campos": {"auto_a_nombre_propio": True}}, "eligibility"))
    stub_ollama.queue("{not json", valid)
    service(tmp_path, "record", stub_ollama).extract(REQ)
    (path,) = (tmp_path / "llm" / "_recording" / "extract").glob("*.json")
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["response"]["campos"]["auto_a_nombre_propio"] is True
    assert (record["prompt_tokens"], record["completion_tokens"]) == (812, 64)  # one attempt, not the sum


@pytest.mark.req("FR-080")
def test_invalid_output_is_not_recorded(tmp_path, stub_ollama):
    stub_ollama.queue("{not json", "{still not json")
    with pytest.raises(InvalidModelOutput):
        service(tmp_path, "record", stub_ollama).extract(REQ)
    assert files(tmp_path / "llm") == []


def test_fake_never_reads_the_recording_dir(tmp_path, stub_ollama):
    service(tmp_path, "record", stub_ollama).extract(REQ)

    def no_ollama():
        raise AssertionError("fake mode must not create an Ollama client")

    fake = LlmService("fake", tmp_path / "llm", SCHEMAS, no_ollama, model="gemma4:12b", ocr_model="glm-ocr",
                      record_dir=tmp_path / "llm" / "_recording")
    assert fake.extract(REQ).fixture_hit is False
