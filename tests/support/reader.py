"""Document Intelligence double for actions_api tool tests: answers by requested type with Laura's
documents (or an override), following the doc_intel contract."""

import base64
import itertools

from contracts.documents import DocumentExtractResponse, ExtractedField

LAURA_DOCS = {
    "identification": ("identification", {"nombre_completo": "LAURA MÉNDEZ ROJAS", "vigencia": 2031}),
    "payslip": ("payslip", {"nombre_completo": "LAURA MÉNDEZ ROJAS", "ingreso_neto": 10000.0, "periodicidad": "quincenal",
                            "periodo_inicio": "2026-09-16", "periodo_fin": "2026-09-30",
                            "fecha_emision": "2026-09-30", "moneda": "MXN"}),
    "proof_of_address": ("proof_of_address", {"domicilio": "AV MORELOS 245, CENTRO, TOLUCA, MÉX.",
                                              "codigo_postal": "50000", "fecha_emision": "2026-09-05"}),
    "vehicle_invoice": ("vehicle_invoice", {"nombre_completo": "LAURA MÉNDEZ ROJAS", "marca": "VOLKSWAGEN",
                                            "modelo": "JETTA", "anio": 2019}),
}
LOW_PAYSLIP = {**LAURA_DOCS["payslip"][1], "ingreso_neto": 7000.0}
_counter = itertools.count()


class LauraReader:
    def __init__(self):
        self.overrides: dict[str, dict] = {}

    def extract(self, expected_type, mime_type, content_base64):
        detected, fields = LAURA_DOCS[expected_type]
        fields = self.overrides.get(expected_type, fields)
        return DocumentExtractResponse(
            detected_type=detected, type_matches=True, is_test_specimen=True,
            fields={k: ExtractedField(value=v, confidence=0.95) for k, v in fields.items()}, ocr_chars=300,
        )


def submit(case, requested_type: str):
    content = base64.b64encode(f"{requested_type}-{next(_counter)}".encode()).decode()
    return case.call("submit_document", {"requested_type": requested_type, "filename": f"{requested_type}.png",
                                         "content_base64": content})


def install(api) -> LauraReader:
    reader = LauraReader()
    api.client.app.state.services.extras["document_reader"] = reader
    return reader
