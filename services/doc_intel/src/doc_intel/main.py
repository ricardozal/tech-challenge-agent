"""Document Intelligence: OCR → extraction → per-field confidence. Stateless, no database (Principle III)."""

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from contracts.common import ErrorBody, ErrorDetail
from contracts.documents import DocumentExtractRequest, DocumentExtractResponse, ExtractedField
from contracts.llm import ExtractRequest, OcrRequest, document_type_to_domain
from doc_intel.confidence import confidence, normalize
from doc_intel.gateway_client import GatewayClient, UpstreamFailure

SPECIMEN_MARKS = ("ESPECIMEN DE PRUEBA", "DATOS FICTICIOS", "DOCUMENTO DE PRUEBA")


def create_app(gateway: GatewayClient | None = None) -> FastAPI:
    gateway = gateway or GatewayClient(os.environ.get("LLM_URL", "http://localhost:8002"))
    app = FastAPI(title="Document Intelligence")

    @app.exception_handler(UpstreamFailure)
    async def _upstream(_, exc: UpstreamFailure) -> JSONResponse:
        body = ErrorBody(error=ErrorDetail(code="upstream_failure", message=str(exc)))
        return JSONResponse(status_code=502, content=body.model_dump())

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/v1/documents/extract", response_model=DocumentExtractResponse)
    def extract(req: DocumentExtractRequest) -> DocumentExtractResponse:
        ocr = gateway.ocr(OcrRequest(content_base64=req.content_base64, mime_type=req.mime_type))
        extraction = gateway.extract(ExtractRequest(schema_name="documento", text=ocr.text))
        data = extraction.data
        detected = document_type_to_domain(data.get("tipo_documento"))
        fields = {
            name: ExtractedField(value=value, confidence=confidence(name, value, ocr.text))
            for name, value in (data.get("campos") or {}).items()
        }
        norm = normalize(ocr.text)
        return DocumentExtractResponse(
            detected_type=detected,
            type_matches=detected == req.expected_type,
            is_test_specimen=any(mark in norm for mark in SPECIMEN_MARKS),
            fields=fields,
            ocr_chars=len(ocr.text),
        )

    return app


app = create_app()
