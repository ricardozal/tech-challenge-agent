"""TOOL spans of Deps.call_tool and the `turn` span on failure (contracts/tracing.md, O-03, O-05).

Against the real compose services (LLM_MODE=fake); the exporter is OpenTelemetry's in-memory one.
"""

import dataclasses
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from agent.clients import ActionsClient, LlmClient
from agent.config import Settings
from agent.graph import Deps
from agent.main import UPSTREAM_MESSAGE, create_app


@pytest.fixture
def traced():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter


def new_case(stack) -> dict:
    case_id = stack["http"].post(f"{stack['agent']}/cases", headers={"Idempotency-Key": f"t-{uuid.uuid4()}"}).json()[
        "case_id"]
    case = stack["http"].get(f"{stack['actions']}/cases/{case_id}").json()
    return {"case_id": case_id, "kind": "message", "message_id": f"m-{uuid.uuid4().hex[:12]}", "step": 0,
            "case": {"id": case_id, "stage": case["stage"], "status": case["status"], "version": case["version"]}}


def tool_spans(exporter):
    return [s for s in exporter.get_finished_spans() if s.attributes.get("openinference.span.kind") == "TOOL"]


@pytest.mark.req("FR-088")
@pytest.mark.req("FR-090")
async def test_rejected_tool_is_an_error_span_with_its_code(stack, traced):
    tracer, exporter = traced
    state = new_case(stack)  # a new case is in eligibility; select_option is only allowed in simulation
    deps = Deps(actions=ActionsClient(stack["actions"]), llm=LlmClient("http://unused"), tracer=tracer)
    result, _ = await deps.call_tool(state, "select_option", {"option_id": "opt-1"})
    assert result.rejection.code == "forbidden"

    (span,) = tool_spans(exporter)
    assert span.attributes["tool.name"] == "select_option"
    assert span.status.status_code == StatusCode.ERROR and span.status.description == "forbidden"
    output = json.loads(span.attributes["output.value"])
    assert output["outcome"] == "rejected" and output["rejection_code"] == "forbidden"
    assert json.loads(span.attributes["input.value"]) == {"option_id": "opt-1"}
    meta = json.loads(span.attributes["metadata"])
    assert meta["actor"] == "agent" and meta["idempotency_key"].endswith(":select_option")


@pytest.mark.req("FR-093")
async def test_tool_input_is_redacted(stack, traced):
    tracer, exporter = traced
    state = new_case(stack)
    deps = Deps(actions=ActionsClient(stack["actions"]), llm=LlmClient("http://unused"), tracer=tracer)
    text = "mi CURP es MERL880412MMCNJR09"
    await deps.call_tool(state, "append_message", {"message_id": state["message_id"], "author": "client",
                                                   "text": text, "intent": "proporcionar_datos"})
    (span,) = tool_spans(exporter)
    assert "MERL880412MMCNJR09" not in span.attributes["input.value"]
    assert "[REDACTED_CURP]" in span.attributes["input.value"]
    assert span.status.status_code != StatusCode.ERROR


@pytest.mark.req("FR-090")
def test_turn_span_is_an_error_when_the_model_does_not_answer(stack, traced):
    """Edge case "Modelo lento": an upstream failure or timeout ends the turn with a clear error in the trace."""
    tracer, exporter = traced
    settings = dataclasses.replace(Settings.from_env(), llm_url="http://127.0.0.1:9")  # closed port
    case_id = new_case(stack)["case_id"]  # created by the compose agent, whose gateway works
    with TestClient(create_app(settings, tracer=tracer)) as client:
        resp = client.post(f"/cases/{case_id}/messages", json={"text": "hola"},
                           headers={"Idempotency-Key": f"t-{uuid.uuid4()}"})
    assert resp.status_code == 502
    assert resp.json()["error"] == {"code": "upstream_failure", "message": UPSTREAM_MESSAGE, "details": {}}
    turns = [s for s in exporter.get_finished_spans() if s.name == "turn" and s.attributes.get("session.id") == case_id]
    assert len(turns) == 1
    assert turns[0].status.status_code == StatusCode.ERROR
    assert "llm_gateway" in turns[0].status.description  # the technical detail stays in the trace


@pytest.mark.req("FR-090")
def test_upstream_failure_message_is_spanish_without_technical_detail():
    """Constitution X: the client never sees class names, services or URLs."""
    assert UPSTREAM_MESSAGE.startswith("No pude responderte")
    for technical in ("Error", "Timeout", "llm_gateway", "actions_api", "http", "HTTP"):
        assert technical not in UPSTREAM_MESSAGE
