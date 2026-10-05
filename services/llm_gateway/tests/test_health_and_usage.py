"""/health checks the installed models in real modes (O-15); fixture usage counters in fake (O-12)."""

import json

import pytest
from fastapi.testclient import TestClient

from contracts.llm import ExtractRequest, fixture_key
from llm_gateway.config import REPO_ROOT
from llm_gateway.main import create_app
from llm_gateway.modes import LlmService, extract_inputs
from llm_gateway.schemas import Schemas

SCHEMAS = Schemas(REPO_ROOT / "eval" / "esquemas.json")


def client(tmp_path, mode, stub) -> TestClient:
    svc = LlmService(mode, tmp_path, SCHEMAS, lambda: stub, model="gemma4:12b", ocr_model="glm-ocr")
    return TestClient(create_app(service=svc))


@pytest.mark.req("FR-084")
@pytest.mark.parametrize("mode", ["ollama", "record"])
def test_health_is_503_naming_the_missing_model(tmp_path, stub_ollama, mode):
    stub_ollama.models = ["gemma4:12b"]
    resp = client(tmp_path, mode, stub_ollama).get("/health")
    assert resp.status_code == 503
    assert resp.json() == {
        "status": "error",
        "mode": mode,
        "missing_models": ["glm-ocr"],
        "message": "Falta el modelo glm-ocr en Ollama. Instálalo con: ollama pull glm-ocr",
    }


@pytest.mark.req("FR-084")
def test_health_is_503_with_both_models_when_ollama_does_not_answer(tmp_path, stub_ollama):
    stub_ollama.models = ConnectionError("connection refused")
    resp = client(tmp_path, "ollama", stub_ollama).get("/health")
    assert resp.status_code == 503
    assert resp.json()["missing_models"] == ["gemma4:12b", "glm-ocr"]


def test_health_is_ok_with_both_models(tmp_path, stub_ollama):
    resp = client(tmp_path, "ollama", stub_ollama).get("/health")
    assert resp.status_code == 200 and resp.json()["status"] == "ok"


def test_fake_mode_never_checks_ollama(tmp_path, stub_ollama):
    stub_ollama.models = AssertionError("fake mode must not ask Ollama for its models")
    assert client(tmp_path, "fake", stub_ollama).get("/health").status_code == 200


@pytest.mark.req("FR-084")
def test_an_ollama_failure_is_an_error_not_a_recorded_answer(tmp_path, stub_ollama):
    def down(*_):
        raise ConnectionError("connection refused")

    stub_ollama.chat_json = down
    resp = client(tmp_path, "ollama", stub_ollama).post("/v1/extract", json={"schema_name": "mensaje", "text": "hola"})
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "upstream_failure"


def _write(tmp_path, text: str, origin: str | None) -> str:
    req = ExtractRequest(schema_name="mensaje", stage="eligibility", agent_question="?", text=text)
    key = fixture_key("extract", "mensaje", extract_inputs(req), SCHEMAS.version)
    record = {"request": {}, "response": {"intencion": "otro", "campos": {}}}
    if origin:
        record["origin"] = origin
    (tmp_path / "extract").mkdir(exist_ok=True)
    (tmp_path / "extract" / f"{key}.json").write_text(json.dumps(record))
    return key


@pytest.mark.req("FR-083")
def test_usage_counts_recorded_seeded_and_missing_answers(tmp_path, stub_ollama):
    recorded, seeded = _write(tmp_path, "grabado", "recorded"), _write(tmp_path, "sembrado", None)
    http = client(tmp_path, "fake", stub_ollama)
    for text in ("grabado", "sembrado", "nadie lo grabó", "grabado"):
        body = {"schema_name": "mensaje", "stage": "eligibility", "agent_question": "?", "text": text}
        assert http.post("/v1/extract", json=body).status_code == 200

    usage = http.get("/v1/fixtures/usage").json()
    assert usage["mode"] == "fake"
    assert usage["counts"] == {"recorded": 2, "seeded": 1, "missing": 1}
    assert usage["by_task"]["extract"]["recorded"] == [recorded]
    assert usage["by_task"]["extract"]["seeded"] == [seeded]
    assert len(usage["by_task"]["extract"]["missing"]) == 1

    assert http.delete("/v1/fixtures/usage").status_code == 204
    assert http.get("/v1/fixtures/usage").json()["counts"] == {"recorded": 0, "seeded": 0, "missing": 0}


@pytest.mark.req("FR-083")
def test_usage_is_not_counted_in_real_modes(tmp_path, stub_ollama):
    http = client(tmp_path, "ollama", stub_ollama)
    http.post("/v1/extract", json={"schema_name": "mensaje", "text": "hola"})
    assert http.get("/v1/fixtures/usage").json()["counts"] == {"recorded": 0, "seeded": 0, "missing": 0}


@pytest.mark.req("FR-084")
def test_an_ollama_timeout_is_a_clear_upstream_failure(tmp_path, stub_ollama):
    import httpx

    def slow(*_):
        raise httpx.ReadTimeout("timed out")

    stub_ollama.chat_text = slow
    resp = client(tmp_path, "ollama", stub_ollama).post(
        "/v1/reply", json={"stage": "eligibility", "status": "active", "next_question": "¿Qué auto es?"})
    assert resp.status_code == 502
    assert resp.json()["error"] == {"code": "upstream_failure", "message": "Ollama no respondió a tiempo: ReadTimeout",
                                    "details": {}}
