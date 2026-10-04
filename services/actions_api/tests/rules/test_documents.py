"""Validity, income proof type, vehicle ownership and low confidence (pure, FR-030 to FR-033)."""

import pytest

from actions_api.config import REPO_ROOT
from actions_api.policy import PolicyRegistry
from actions_api.rules.documents import (
    REQUIRED_KEYS,
    validate_income_proof_type,
    validate_vehicle_ownership,
    validations_for,
)
from actions_api.rules.validity import validate_validity
from contracts.case import CaseState, Declared, Vehicle
from contracts.common import DocumentType, Employment
from tests.support.documents import LAURA, NOW, TODAY, doc, payslip

POLICY = PolicyRegistry.load(REPO_ROOT / "policy").current()
JETTA = Vehicle(make="Volkswagen", model="Jetta", year=2019, own_name=True, declared_debt=False, spare_key=True)


def invoice(**overrides):
    fields = dict(full_name="LAURA MÉNDEZ ROJAS", make="VOLKSWAGEN", model="JETTA", year=2019, vin="3VWEJ1BU0KM123456")
    fields.update(overrides)
    return doc(DocumentType.vehicle_invoice, **fields)


@pytest.mark.req("FR-030")
def test_identification_validity_year():
    assert validate_validity(doc(DocumentType.identification, valid_until=2031), "validity@identification",
                             POLICY, TODAY, NOW).result == "passed"
    v = validate_validity(doc(DocumentType.identification, valid_until=2025), "validity@identification", POLICY, TODAY, NOW)
    assert v.result == "mismatch" and v.detail["reason"] == "expired"


@pytest.mark.req("FR-030")
def test_proofs_older_than_three_months_are_rejected():
    recent = doc(DocumentType.proof_of_address, issue_date="2026-07-05")
    old = doc(DocumentType.proof_of_address, issue_date="2026-07-03")
    assert validate_validity(recent, "validity@proof_of_address", POLICY, TODAY, NOW).result == "passed"
    v = validate_validity(old, "validity@proof_of_address", POLICY, TODAY, NOW)
    assert v.result == "mismatch" and v.detail["reason"] == "too_old"


@pytest.mark.req("FR-031")
def test_self_employed_cannot_prove_income_with_a_payslip():
    v = validate_income_proof_type(Employment.self_employed, payslip(), POLICY, NOW)
    assert v.result == "mismatch" and v.detail["reason"] == "proof_not_accepted"
    assert validate_income_proof_type(Employment.employed, payslip(), POLICY, NOW).result == "passed"


@pytest.mark.req("FR-032")
def test_invoice_holder_and_vehicle_must_match():
    assert validate_vehicle_ownership(LAURA, JETTA, invoice(), POLICY, NOW).result == "passed"
    holder = validate_vehicle_ownership(LAURA, JETTA, invoice(full_name="JORGE RAMÍREZ LUNA"), POLICY, NOW)
    assert holder.result == "mismatch" and holder.detail["reason"] == "holder_mismatch"
    vehicle = validate_vehicle_ownership(LAURA, JETTA, invoice(year=2018), POLICY, NOW)
    assert vehicle.result == "mismatch" and vehicle.detail["reason"] == "vehicle_mismatch"


@pytest.mark.req("FR-033")
def test_low_confidence_field_is_not_used():
    v = validate_vehicle_ownership(LAURA, JETTA, invoice().model_copy(update={"fields": {
        **invoice().fields, "full_name": invoice().fields["full_name"].model_copy(update={"confidence": 0.6})}}),
        POLICY, NOW)
    assert v.result == "low_confidence" and v.detail["fields"] == ["full_name"]
    assert "observed" not in v.detail


def test_each_document_type_produces_its_validations():
    state = CaseState(client=LAURA, vehicle=JETTA, declared=Declared(employment="employed", income_amount="20000",
                                                                     income_periodicity="monthly"))
    keys = {
        t: [v.key for v in validations_for(d, state, POLICY, TODAY, NOW)]
        for t, d in {
            "identification": doc(DocumentType.identification, full_name="LAURA MÉNDEZ ROJAS", valid_until=2031),
            "payslip": payslip(),
            "proof_of_address": doc(DocumentType.proof_of_address, address="AV MORELOS 245, CENTRO, TOLUCA",
                                    postal_code="50000", issue_date="2026-09-05"),
            "vehicle_invoice": invoice(),
        }.items()
    }
    assert keys == {
        "identification": ["name@identification", "validity@identification"],
        "payslip": ["income", "income_proof_type", "name@income_proof", "validity@income_proof"],
        "proof_of_address": ["address@proof_of_address", "validity@proof_of_address"],
        "vehicle_invoice": ["vehicle_ownership"],
    }
    assert sorted(k for ks in keys.values() for k in ks) == sorted(REQUIRED_KEYS)
