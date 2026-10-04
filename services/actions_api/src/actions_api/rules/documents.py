"""Document validations (FR-028 to FR-033): which ones run for each document type. Pure."""

from datetime import date, datetime

from actions_api.policy_model import Policy
from actions_api.rules.fields import low_confidence, take, validation
from actions_api.rules.income import validate_income
from actions_api.rules.matching import name_score, validate_address, validate_name
from actions_api.rules.text import normalize
from actions_api.rules.validity import validate_validity
from contracts.case import CaseState, ClientData, DocumentRecord, Validation, Vehicle
from contracts.common import DocumentType, Employment, ValidationResult, ValidationType

INCOME_PROOFS = (DocumentType.payslip, DocumentType.bank_statement)

# Validations the gate requires (data-model.md § Validaciones requeridas por el gate).
REQUIRED_KEYS = (
    "income",
    "income_proof_type",
    "name@identification",
    "name@income_proof",
    "address@proof_of_address",
    "validity@identification",
    "validity@income_proof",
    "validity@proof_of_address",
    "vehicle_ownership",
)


def validate_income_proof_type(employment: Employment, doc: DocumentRecord, policy: Policy, now: datetime) -> Validation:
    accepted = policy.income.accepted_proofs.get(employment, [])
    ok = doc.detected_type in accepted
    return validation(
        "income_proof_type", ValidationType.income_proof_type,
        ValidationResult.passed if ok else ValidationResult.mismatch, doc, policy, now,
        reason=None if ok else "proof_not_accepted", employment=employment.value,
        proof_type=doc.detected_type.value, accepted=[a.value for a in accepted],
    )


def validate_vehicle_ownership(
    client: ClientData, vehicle: Vehicle, doc: DocumentRecord, policy: Policy, now: datetime
) -> Validation:
    key, vtype = "vehicle_ownership", ValidationType.vehicle_ownership
    taken = take(doc, ("full_name", "make", "model", "year"), policy)
    if taken.low:
        return low_confidence(key, vtype, doc, taken.low, policy, now)
    threshold = float(policy.matching.name_similarity_threshold)
    if name_score(client.full_name, taken.values["full_name"]) < threshold:
        return validation(key, vtype, ValidationResult.mismatch, doc, policy, now, ["full_name"],
                          reason="holder_mismatch")
    same_vehicle = (
        normalize(vehicle.make) == normalize(taken.values["make"])
        and normalize(vehicle.model) == normalize(taken.values["model"])
        and str(vehicle.year) == str(taken.values["year"])
    )
    if not same_vehicle:
        return validation(key, vtype, ValidationResult.mismatch, doc, policy, now, ["make", "model", "year"],
                          reason="vehicle_mismatch",
                          declared=f"{vehicle.make} {vehicle.model} {vehicle.year}",
                          invoice=f"{taken.values['make']} {taken.values['model']} {taken.values['year']}")
    return validation(key, vtype, ValidationResult.passed, doc, policy, now, ["full_name", "make", "model", "year"])


def validations_for(doc: DocumentRecord, state: CaseState, policy: Policy, today: date, now: datetime) -> list[Validation]:
    """Validations that one document produces, by its detected type."""
    kind = doc.detected_type
    if kind == DocumentType.identification:
        return [
            validate_name(state.client, doc, "name@identification", policy, now),
            validate_validity(doc, "validity@identification", policy, today, now),
        ]
    if kind in INCOME_PROOFS:
        return [
            validate_income(state.declared, doc, policy, now),
            validate_income_proof_type(state.declared.employment, doc, policy, now),
            validate_name(state.client, doc, "name@income_proof", policy, now),
            validate_validity(doc, "validity@income_proof", policy, today, now),
        ]
    if kind == DocumentType.proof_of_address:
        return [
            validate_address(state.client, doc, policy, now),
            validate_validity(doc, "validity@proof_of_address", policy, today, now),
        ]
    if kind == DocumentType.vehicle_invoice:
        return [validate_vehicle_ownership(state.client, state.vehicle, doc, policy, now)]
    return []
