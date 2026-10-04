"""LLM Gateway: /v1/extract, /v1/ocr, /v1/reply. Only service that talks to Ollama (Principle III)."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ollama import ResponseError

from contracts.common import ErrorBody, ErrorDetail
from contracts.llm import ExtractRequest, ExtractResponse, OcrRequest, OcrResponse, ReplyRequest, ReplyResponse
from llm_gateway.config import Settings
from llm_gateway.modes import FixtureMissing, InvalidModelOutput, LlmService
from llm_gateway.ollama_client import OllamaClient
from llm_gateway.schemas import Schemas


def _error(status: int, code: str, message: str) -> JSONResponse:
    body = ErrorBody(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status, content=body.model_dump())


def create_app(settings: Settings | None = None, service: LlmService | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    service = service or LlmService(
        mode=settings.mode,
        fixtures_dir=settings.fixtures_dir,
        schemas=Schemas(settings.esquemas_path),
        client_factory=lambda: OllamaClient(settings.ollama_url, settings.model, settings.ocr_model),
        model=settings.model,
        ocr_model=settings.ocr_model,
    )
    app = FastAPI(title="LLM Gateway")
    app.state.service = service

    @app.exception_handler(FixtureMissing)
    async def _fixture_missing(_: Request, exc: FixtureMissing) -> JSONResponse:
        return _error(404, "fixture_missing", f"No hay fixture grabado para esta solicitud ({exc}).")

    @app.exception_handler(InvalidModelOutput)
    async def _invalid_output(_: Request, exc: InvalidModelOutput) -> JSONResponse:
        return _error(502, "invalid_model_output", str(exc))

    @app.exception_handler(ConnectionError)
    async def _upstream(_: Request, exc: ConnectionError) -> JSONResponse:
        return _error(502, "upstream_failure", f"Ollama no respondió: {exc}")

    @app.exception_handler(ResponseError)
    async def _ollama_error(_: Request, exc: ResponseError) -> JSONResponse:
        return _error(502, "upstream_failure", f"Ollama respondió con error: {exc.error}")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "mode": service.mode, "schema_version": service.schemas.version}

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
