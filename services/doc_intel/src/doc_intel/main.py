"""Document Intelligence: OCR → extraction → per-field confidence. Stateless, no database (Principle III)."""

import base64
import hashlib
import json
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from contracts.common import ErrorBody, ErrorDetail
from contracts.documents import DocumentExtractRequest, DocumentExtractResponse, ExtractedField
from contracts.llm import ExtractRequest, OcrRequest, document_type_to_domain
from doc_intel.confidence import confidence, normalize
from doc_intel import telemetry
from doc_intel.gateway_client import GatewayClient, UpstreamFailure

SPECIMEN_MARKS = ("ESPECIMEN DE PRUEBA", "DATOS FICTICIOS", "DOCUMENTO DE PRUEBA")


def create_app(gateway: GatewayClient | None = None, tracer: trace.Tracer | None = None) -> FastAPI:
    app = FastAPI(title="Document Intelligence", telemetry=telemetry.FASTAPI_TELEMETRY_OFF)
    telemetry.setup(app)  # before the gateway client, so its calls carry the trace context
    gateway = gateway or GatewayClient(os.environ.get("LLM_URL", "http://localhost:8002"))

    @app.exception_handler(UpstreamFailure)
    async def _upstream(_, exc: UpstreamFailure) -> JSONResponse:
        body = ErrorBody(error=ErrorDetail(code="upstream_failure", message=str(exc)))
        return JSONResponse(status_code=502, content=body.model_dump())

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/v1/documents/extract", response_model=DocumentExtractResponse)
    def extract(req: DocumentExtractRequest) -> DocumentExtractResponse:
        with (tracer or trace.get_tracer("doc_intel")).start_as_current_span(
            "read_document", record_exception=False, set_status_on_exception=False
        ) as span:
            # Span `read_document` (contracts/tracing.md): type and confidence, never the field values.
            sha256 = hashlib.sha256(base64.b64decode(req.content_base64)).hexdigest()
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
            span.set_attribute(SpanAttributes.INPUT_VALUE, json.dumps(
                {"requested_type": req.expected_type.value, "mime_type": req.mime_type, "sha256": sha256}))
            try:
                result = _read(req)
            except UpstreamFailure as exc:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, json.dumps({
                "detected_type": result.detected_type.value,
                "fields": {name: {"confidence": f.confidence} for name, f in result.fields.items()},
            }))
            return result

    def _read(req: DocumentExtractRequest) -> DocumentExtractResponse:
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
