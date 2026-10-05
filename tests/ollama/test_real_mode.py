"""Real models (LLM_MODE=ollama): gemma4:12b and glm-ocr behind the gateway, demos and free text.

Run with `LLM_MODE=ollama make up && make test-ollama`; excluded from the default pytest run.
"""

import base64
import uuid
from pathlib import Path

import httpx
import pytest

from scripts.run_demo import play
from tests.conftest import ACTIONS_URL, AGENT_URL, LLM_URL

pytestmark = pytest.mark.ollama

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "fixtures" / "scenarios").glob("*.yaml"))


@pytest.fixture(scope="module")
def real_gateway(compose_up):
    health = httpx.get(f"{LLM_URL}/health", timeout=10).json()
    if health.get("mode") != "ollama":
        pytest.skip("the gateway is not in LLM_MODE=ollama")
    return health


@pytest.mark.req("FR-077")
def test_gateway_uses_gemma_and_glm_ocr(real_gateway):
    assert (real_gateway["model"], real_gateway["ocr_model"]) == ("gemma4:12b", "glm-ocr")
    image = (ROOT / "fixtures" / "documents" / "laura_identification.png").read_bytes()
    resp = httpx.post(f"{LLM_URL}/v1/ocr", json={"content_base64": base64.b64encode(image).decode()}, timeout=330)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["text"].strip() and body["model"] == "glm-ocr" and body["fixture_hit"] is False


@pytest.mark.req("FR-078")
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda p: p.stem)
def test_demo_reaches_its_outcome_with_real_models(real_gateway, scenario):
    play(scenario, quiet=True)  # raises DemoFailure if status, stage, tools or events differ


@pytest.mark.req("FR-079")
def test_free_text_outside_the_script_is_understood(real_gateway):
    with httpx.Client(timeout=330) as http:
        case_id = http.post(f"{AGENT_URL}/cases", headers={"Idempotency-Key": f"free-{uuid.uuid4()}"}).json()["case_id"]

        def send(text: str) -> dict:
            resp = http.post(f"{AGENT_URL}/cases/{case_id}/messages", json={"text": text},
                             headers={"Idempotency-Key": f"free-{uuid.uuid4()}"})
            assert resp.status_code == 200, resp.text
            return resp.json()

        send("Hola, soy Laura Méndez Rojas")
        assert http.get(f"{AGENT_URL}/cases/{case_id}/conversation").json()["state"]["last_question"].startswith(
            "¿Qué auto es?")
        turn = send("es un Nissan Versa 2020, lo compré de agencia")
        accepted = [c["tool"] for c in turn["tool_calls"] if c["outcome"] == "accepted"]
        assert "update_declared_data" in accepted, turn["tool_calls"]
        vehicle = http.get(f"{ACTIONS_URL}/cases/{case_id}").json()["state"]["vehicle"]
        assert (vehicle["make"], vehicle["model"], vehicle["year"]) == ("Nissan", "Versa", 2020)
