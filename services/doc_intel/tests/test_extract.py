"""POST /v1/documents/extract with a gateway double (doc_intel is the unit under test)."""

import base64

import pytest
from fastapi.testclient import TestClient

from contracts.llm import ExtractResponse, OcrResponse
from doc_intel.gateway_client import UpstreamFailure
from doc_intel.main import create_app

OCR_TEXT = "RECIBO DE NÓMINA — ESPÉCIMEN DE PRUEBA\nEMPLEADO LAURA MÉNDEZ ROJAS\nNETO A PAGAR $10,000.00 MXN"


class Gateway:
    def __init__(self, tipo="recibo_nomina", fail=False):
        self.tipo, self.fail, self.requests = tipo, fail, []

    def ocr(self, req):
        if self.fail:
            raise UpstreamFailure("llm_gateway /v1/ocr: HTTP 404")
        return OcrResponse(text=OCR_TEXT, model="glm-ocr", mode="fake", fixture_hit=True)

    def extract(self, req):
        self.requests.append(req)
        campos = {"nombre_completo": "LAURA MÉNDEZ ROJAS", "ingreso_neto": 10000.0, "moneda": "MXN", "curp": None}
        return ExtractResponse(data={"tipo_documento": self.tipo, "campos": campos}, schema_name="documento",
                               schema_version=3, model="gemma4:12b", mode="fake", fixture_hit=True)


def post(gateway, expected="payslip"):
    client = TestClient(create_app(gateway))
    return client.post("/v1/documents/extract", json={"expected_type": expected,
                                                      "content_base64": base64.b64encode(b"png").decode()})


@pytest.mark.req("FR-026")
def test_returns_type_and_each_field_with_confidence():
    gateway = Gateway()
    body = post(gateway).json()
    assert body["detected_type"] == "payslip" and body["type_matches"] is True
    assert body["fields"]["nombre_completo"] == {"value": "LAURA MÉNDEZ ROJAS", "confidence": 0.95}
    assert body["fields"]["ingreso_neto"]["confidence"] == 0.95
    assert body["fields"]["curp"] == {"value": None, "confidence": 0.0}
    assert body["is_test_specimen"] is True
    assert gateway.requests[0].schema_name == "documento" and gateway.requests[0].text == OCR_TEXT


@pytest.mark.req("FR-026")
def test_document_of_another_type_is_flagged():
    body = post(Gateway(tipo="estado_cuenta")).json()
    assert body["detected_type"] == "bank_statement" and body["type_matches"] is False


def test_gateway_failure_is_a_502():
    resp = post(Gateway(fail=True))
    assert resp.status_code == 502 and resp.json()["error"]["code"] == "upstream_failure"
