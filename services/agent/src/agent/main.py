"""Channel API of the agent (contracts/agent-channel.md, FR-001)."""

import base64
import hashlib
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from openinference.instrumentation import using_session
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import trace
from opentelemetry.trace import Status as SpanStatus
from opentelemetry.trace import StatusCode

from agent import telemetry
from agent.clients import ActionsClient, LlmClient, UpstreamError
from agent.config import Settings
from agent.graph import Deps, TurnState, build_graph
from agent.turn_lock import CaseBusy, TurnStore
from contracts.actions import ToolContext
from contracts.channel import (
    Conversation,
    ConversationMessage,
    CreateCaseResponse,
    MessageIn,
    ToolCallSummary,
    TurnCase,
    TurnResponse,
)
from contracts.common import DocumentType, ErrorBody, ErrorDetail
from contracts.redaction import redact


# What the client reads when a service does not answer (Constitution X: Spanish, no technical detail).
# The detail (service, exception) stays in the `turn` span and in the agent log.
UPSTREAM_MESSAGE = (
    "No pude responderte en este momento porque un servicio tardó demasiado o no respondió. "
    "Intenta de nuevo en unos segundos."
)
log = logging.getLogger("agent")


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=ErrorBody(error=ErrorDetail(code=code, message=message)).model_dump())


def _message_id(case_id: UUID, idempotency_key: str) -> str:
    return "m-" + hashlib.sha256(f"{case_id}:{idempotency_key}".encode()).hexdigest()[:12]


def create_app(settings: Settings | None = None, tracer: trace.Tracer | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    telemetry.setup()
    tracer = tracer or telemetry.tracer()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store = TurnStore(settings.database_url)
        await store.open()
        actions = ActionsClient(settings.actions_url)
        llm = LlmClient(settings.llm_url)
        async with AsyncPostgresSaver.from_conn_string(settings.database_url) as saver:
            await saver.setup()
            app.state.store = store
            app.state.actions = actions
            app.state.graph = build_graph(Deps(actions=actions, llm=llm, tracer=tracer), saver)
            yield
        await actions.aclose()
        await llm.aclose()
        await store.close()

    app = FastAPI(title="Agent channel", lifespan=lifespan, telemetry=telemetry.FASTAPI_TELEMETRY_OFF)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.web_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key"],
        allow_credentials=False,
    )

    async def run_turn(case_id: UUID, kind: str, message_id: str, **inputs: Any) -> TurnResponse:
        """One turn = one trace (O-03): the root span `turn` wraps the whole graph run."""
        with using_session(str(case_id)), tracer.start_as_current_span(
            "turn", record_exception=False, set_status_on_exception=False
        ) as span:
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.AGENT.value)
            span.set_attribute(SpanAttributes.SESSION_ID, str(case_id))
            meta: dict[str, Any] = {"case_id": str(case_id), "message_id": message_id, "kind": kind}
            document = inputs.get("document") or {}
            text = inputs.get("text") or (f"documento: {document.get('requested_type')}" if document else "")
            try:
                view = await app.state.actions.get_case(case_id)
                names = [view.state.client.full_name] if view.state.client.full_name else []
                meta.update(stage_before=view.stage.value, status_before=view.status.value)
                span.set_attribute(SpanAttributes.INPUT_VALUE, redact(text, names))
                turn, learned_name = await _run_graph(case_id, kind, message_id, view, **inputs)
                names += [learned_name] if learned_name else []
            except Exception as exc:
                span.set_status(SpanStatus(StatusCode.ERROR, f"{type(exc).__name__}: {exc}"))
                raise
            finally:
                span.set_attribute(SpanAttributes.METADATA, json.dumps(meta))
            meta.update(stage_after=turn.case.stage, status_after=turn.case.status, version_after=turn.case.version)
            span.set_attribute(SpanAttributes.METADATA, json.dumps(meta, default=str))
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, redact(turn.reply, names))
            return turn

    async def _run_graph(
        case_id: UUID, kind: str, message_id: str, view: Any, **inputs: Any
    ) -> tuple[TurnResponse, str | None]:
        state: TurnState = {
            "case_id": str(case_id),
            "kind": kind,
            "message_id": message_id,
            "text": inputs.get("text"),
            "document": inputs.get("document"),
            "case": {"id": str(view.id), "stage": view.stage.value, "status": view.status.value, "version": view.version},
            "intent": None,
            "fields": {},
            "facts": {},
            "tool_calls": [],
            "next_question": None,
            "step": 0,
        }
        out = await app.state.graph.ainvoke(state, {"configurable": {"thread_id": str(case_id)}})
        case = out["case"]
        return TurnResponse(
            message_id=message_id,
            reply=out["reply"],
            case=TurnCase(stage=case["stage"], status=case["status"], version=case["version"]),
            tool_calls=[ToolCallSummary(**call) for call in out.get("tool_calls", [])],
        ), (out.get("fields") or {}).get("full_name")

    async def guarded_turn(case_id: UUID, idempotency_key: str, kind: str, **inputs: Any) -> Any:
        stored = await app.state.store.get_processed(case_id, idempotency_key)
        if stored is not None:
            return stored
        try:
            async with app.state.store.case_turn(case_id, settings.case_lock_timeout_s):
                stored = await app.state.store.get_processed(case_id, idempotency_key)
                if stored is not None:
                    return stored
                turn = await run_turn(case_id, kind, _message_id(case_id, idempotency_key), **inputs)
                body = turn.model_dump(mode="json")
                await app.state.store.put_processed(case_id, idempotency_key, body)
                return body
        except CaseBusy:
            return _error(409, "case_busy", "Hay otro mensaje de este caso en proceso; reenvíalo en un momento.")
        except UpstreamError as exc:
            log.warning("upstream_failure case=%s: %s", case_id, exc)
            return _error(502, "upstream_failure", UPSTREAM_MESSAGE)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/cases", status_code=201, response_model=CreateCaseResponse)
    async def create_case(idempotency_key: Annotated[str | None, Header()] = None) -> Any:
        key = idempotency_key or str(uuid4())
        result = await app.state.actions.call("create_case", ToolContext(idempotency_key=f"create:{key}"))
        if result.case is None:
            return _error(502, "upstream_failure", "No se pudo crear el caso.")
        case_id = result.case.id
        turn = await guarded_turn(case_id, f"start:{key}", "start")
        if isinstance(turn, JSONResponse):
            return turn
        return CreateCaseResponse(
            case_id=case_id, reply=turn["reply"], stage=turn["case"]["stage"], status=turn["case"]["status"]
        )

    @app.post("/cases/{case_id}/messages", response_model=TurnResponse)
    async def post_message(case_id: UUID, message: MessageIn, idempotency_key: Annotated[str, Header()]) -> Any:
        return await guarded_turn(case_id, idempotency_key, "message", text=message.text)

    @app.post("/cases/{case_id}/documents", response_model=TurnResponse)
    async def post_document(
        case_id: UUID,
        file: Annotated[UploadFile, File()],
        requested_type: Annotated[DocumentType, Form()],
        idempotency_key: Annotated[str, Header()],
    ) -> Any:
        content = await file.read()
        document = {
            "requested_type": requested_type.value,
            "filename": file.filename or "documento",
            "mime_type": file.content_type or "image/png",
            "content_base64": base64.b64encode(content).decode(),
        }
        return await guarded_turn(case_id, idempotency_key, "document", document=document)

    @app.get("/cases/{case_id}/conversation", response_model=Conversation)
    async def conversation(case_id: UUID) -> Conversation:
        snapshot = await app.state.graph.aget_state({"configurable": {"thread_id": str(case_id)}})
        values = snapshot.values or {}
        return Conversation(
            case_id=case_id,
            messages=[ConversationMessage(**m) for m in values.get("history", [])],
            state={"last_question": values.get("last_question"), "case": values.get("case")},
        )

    return app


app = create_app()
