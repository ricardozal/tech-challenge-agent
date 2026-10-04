"""Corrections of declared data while documents are being validated (spec edge cases, T071)."""

import base64

import pytest

from contracts.documents import DocumentExtractResponse, ExtractedField
from tests.support.cases import documents_case

ADDRESS_FIELDS = {"nombre_completo": "ROBERTO MÉNDEZ SOLÍS", "domicilio": "CALLE HIDALGO 12, SAN SEBASTIÁN, TOLUCA",
                  "codigo_postal": "50090", "fecha_emision": "2026-09-05"}


class Reader:
    def extract(self, expected_type, mime_type, content_base64):
        return DocumentExtractResponse(
            detected_type="proof_of_address", type_matches=True, is_test_specimen=True,
            fields={k: ExtractedField(value=v, confidence=0.95) for k, v in ADDRESS_FIELDS.items()}, ocr_chars=200)


@pytest.mark.req("FR-017")
def test_corrected_income_returns_to_profiling_and_the_option_must_be_chosen_again(api):
    case = documents_case(api)
    resp = case.call("update_declared_data", {"income_amount": "15000"}, on_behalf_of="client")

    assert resp.json()["case"]["stage"] == "profiling"
    state = case.view()["state"]
    assert state["profile"] is None and state["options"] == [] and state["selected_option_id"] is None
    assert state["decisions"][-1]["kind"] == "data_correction"


@pytest.mark.req("FR-028")
def test_corrected_address_is_revalidated_with_the_stored_document(api):
    api.client.app.state.services.extras["document_reader"] = Reader()
    case = documents_case(api)
    case.call("submit_document", {"requested_type": "proof_of_address", "filename": "cfe.png",
                                  "content_base64": base64.b64encode(b"cfe").decode()})
    assert case.view()["state"]["validations"]["address@proof_of_address"]["result"] == "mismatch"

    resp = case.call("update_declared_data", {"address": "Calle Hidalgo 12, San Sebastián, Toluca",
                                              "postal_code": "50090"}, on_behalf_of="client")

    assert resp.json()["result"]["revalidated"] == ["address@proof_of_address"]
    validation = case.view()["state"]["validations"]["address@proof_of_address"]
    assert validation["result"] == "passed" and validation["attempt"] == 2
    assert len(case.view()["state"]["documents"]) == 1  # no new upload
