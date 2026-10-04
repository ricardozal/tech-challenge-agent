"""Enums and shared types (data-model.md § Enums)."""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, PlainSerializer

# Money travels as a decimal string ("12500.00") so no client rounds it (R-17).
Money = Annotated[Decimal, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")]


class Stage(StrEnum):
    eligibility = "eligibility"
    profiling = "profiling"
    simulation = "simulation"
    documents = "documents"


class Status(StrEnum):
    active = "active"
    escalated = "escalated"
    ok_for_lender = "ok_for_lender"
    rejected = "rejected"
    cancelled = "cancelled"


class Actor(StrEnum):
    agent = "agent"
    advisor = "advisor"
    system = "system"


class DocumentType(StrEnum):
    identification = "identification"
    payslip = "payslip"
    bank_statement = "bank_statement"
    proof_of_address = "proof_of_address"
    vehicle_invoice = "vehicle_invoice"
    other = "other"


class Employment(StrEnum):
    employed = "employed"
    self_employed = "self_employed"
    retired = "retired"
    unemployed = "unemployed"


class Periodicity(StrEnum):
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"


class Intent(StrEnum):
    provide_data = "provide_data"
    choose_option = "choose_option"
    question = "question"
    request_human = "request_human"
    cancel = "cancel"
    sensitive_topic = "sensitive_topic"
    other = "other"


class ValidationType(StrEnum):
    income = "income"
    name = "name"
    address = "address"
    validity = "validity"
    income_proof_type = "income_proof_type"
    vehicle_ownership = "vehicle_ownership"


class ValidationResult(StrEnum):
    passed = "passed"
    mismatch = "mismatch"
    low_confidence = "low_confidence"


class ValidationOrigin(StrEnum):
    system = "system"
    manual = "manual"


class RejectionReason(StrEnum):
    owner_mismatch = "owner_mismatch"
    lien_or_debt = "lien_or_debt"
    no_offer_for_profile = "no_offer_for_profile"
    advisor_rejected = "advisor_rejected"


class EscalationReason(StrEnum):
    mismatch_persisted = "mismatch_persisted"
    client_requested_human = "client_requested_human"
    sensitive_topic = "sensitive_topic"
    provider_failure = "provider_failure"
    no_reference_value = "no_reference_value"
    ok_revoked = "ok_revoked"
    policy_unavailable = "policy_unavailable"


class Outcome(StrEnum):
    accepted = "accepted"
    rejected = "rejected"


FINAL_STATUSES = frozenset({Status.ok_for_lender, Status.rejected, Status.cancelled})


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorBody(BaseModel):
    error: ErrorDetail
