"""LLM Gateway: /v1/extract, /v1/ocr, /v1/reply. Only service that talks to Ollama (Principle III)."""

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from ollama import ResponseError

from contracts.common import ErrorBody, ErrorDetail
from contracts.llm import PROMPT_VERSION, ExtractRequest, ExtractResponse, OcrRequest, OcrResponse, ReplyRequest, ReplyResponse
from llm_gateway import telemetry
from llm_gateway.config import Settings
from llm_gateway.modes import FixtureMissing, InvalidModelOutput, LlmService
from llm_gateway.ollama_client import OllamaClient
from llm_gateway.redaction import log_call
from llm_gateway.schemas import Schemas


def _error(status: int, code: str, message: str) -> JSONResponse:
    body = ErrorBody(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status, content=body.model_dump())


def missing_models_message(missing: list[str]) -> str:
    names = " y ".join(missing)
    verb = "Falta el modelo" if len(missing) == 1 else "Faltan los modelos"
    pulls = "; ".join(f"ollama pull {m}" for m in missing)
    return f"{verb} {names} en Ollama. Instálalo con: {pulls}" if len(missing) == 1 else (
        f"{verb} {names} en Ollama (o Ollama no responde). Instálalos con: {pulls}")


def create_app(settings: Settings | None = None, service: LlmService | None = None) -> FastAPI:
    if service is None:
        settings = settings or Settings.from_env()
    service = service or LlmService(
        mode=settings.mode,
        fixtures_dir=settings.fixtures_dir,
        schemas=Schemas(settings.esquemas_path),
        client_factory=lambda: OllamaClient(settings.ollama_url, settings.model, settings.ocr_model),
        model=settings.model,
        ocr_model=settings.ocr_model,
        record_dir=settings.record_dir,
    )
    app = FastAPI(title="LLM Gateway", telemetry=telemetry.FASTAPI_TELEMETRY_OFF)
    telemetry.setup(app)
    app.state.service = service
    real_models = service.mode in ("ollama", "record")

    if real_models and (missing := service.missing_models()):
        # Visible at startup; /health keeps answering 503 until the models are there (O-15).
        log_call(service.log, {"event": "missing_models", "mode": service.mode, "missing_models": missing,
                               "message": missing_models_message(missing)})

    @app.exception_handler(FixtureMissing)
    async def _fixture_missing(_: Request, exc: FixtureMissing) -> JSONResponse:
        return _error(404, "fixture_missing", f"No hay fixture grabado para esta solicitud ({exc}).")

    @app.exception_handler(InvalidModelOutput)
    async def _invalid_output(_: Request, exc: InvalidModelOutput) -> JSONResponse:
        return _error(502, "invalid_model_output", str(exc))

    @app.exception_handler(ConnectionError)
    async def _upstream(_: Request, exc: ConnectionError) -> JSONResponse:
        return _error(502, "upstream_failure", f"Ollama no respondió: {exc}")

    @app.exception_handler(httpx.HTTPError)
    async def _ollama_transport(_: Request, exc: httpx.HTTPError) -> JSONResponse:
        # Timeouts and dropped connections to Ollama are upstream failures, never a 500 (edge case "Modelo lento").
        reason = "no respondió a tiempo" if isinstance(exc, httpx.TimeoutException) else "cortó la conexión"
        return _error(502, "upstream_failure", f"Ollama {reason}: {type(exc).__name__}")

    @app.exception_handler(ResponseError)
    async def _ollama_error(_: Request, exc: ResponseError) -> JSONResponse:
        return _error(502, "upstream_failure", f"Ollama respondió con error: {exc.error}")

    @app.get("/health", response_model=None)
    def health() -> dict | JSONResponse:
        if real_models and (missing := service.missing_models()):
            return JSONResponse(status_code=503, content={
                "status": "error", "mode": service.mode, "missing_models": missing,
                "message": missing_models_message(missing)})
        return {"status": "ok", "mode": service.mode, "schema_version": service.schemas.version,
                "prompt_version": PROMPT_VERSION, "model": service.model, "ocr_model": service.ocr_model}

    @app.get("/v1/fixtures/usage")
    def fixtures_usage() -> dict:
        return service.usage()

    @app.delete("/v1/fixtures/usage", status_code=204)
    def reset_fixtures_usage() -> Response:
        service.reset_usage()
        return Response(status_code=204)

    @app.post("/v1/extract", response_model=ExtractResponse)
    def extract(req: ExtractRequest) -> ExtractResponse:
        return service.extract(req)

    @app.post("/v1/ocr", response_model=OcrResponse)
    def ocr(req: OcrRequest) -> OcrResponse:
        return service.ocr(req)

    @app.post("/v1/reply", response_model=ReplyResponse)
    def reply(req: ReplyRequest) -> ReplyResponse:
        return service.reply(req)

    return app


app = create_app()
