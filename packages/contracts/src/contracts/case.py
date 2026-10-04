"""Case aggregate and read models (data-model.md § Entidades)."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from contracts.common import (
    Actor,
    DocumentType,
    Employment,
    EscalationReason,
    Intent,
    Money,
    Outcome,
    Periodicity,
    Stage,
    Status,
    ValidationOrigin,
    ValidationResult,
    ValidationType,
)
from contracts.documents import ExtractedField


class ClientData(BaseModel):
    """Declared in the conversation; `sources` maps field → message id that provided it (R-16)."""

    full_name: str | None = None
    address: str | None = None  # free text, without postal code
    postal_code: str | None = None
    sources: dict[str, str] = {}


class Declared(BaseModel):
    employment: Employment | None = None
    income_amount: Money | None = None
    income_currency: str = "MXN"
    income_periodicity: Periodicity | None = None
    bureau_consent: bool = False
    bureau_consent_at: datetime | None = None
    bureau_consent_message_id: str | None = None
    sources: dict[str, str] = {}


class VehicleRegistry(BaseModel):
    lien: bool
    reference_value: Money | None = None
    checked_at: datetime


class Vehicle(BaseModel):
    make: str | None = None
    model: str | None = None
    year: int | None = None
    own_name: bool | None = None
    declared_debt: bool | None = None
    spare_key: bool | None = None
    registry: VehicleRegistry | None = None
    sources: dict[str, str] = {}


class KeyQuote(BaseModel):
    amount: Money
    provider_quote_id: str
    quoted_at: datetime
    policy_version: str


class Profile(BaseModel):
    bureau_score: int
    band: str | None = None
    max_amount_profile: Money | None = None
    annual_rate: Money | None = None
    standard_term_months: int | None = None
    max_financeable: Money | None = None
    policy_version: str


class CreditOption(BaseModel):
    id: str
    pct_of_max: Money
    financed_amount: Money
    key_cost: Money
    client_amount: Money
    term_months: int
    annual_rate: Money
    monthly_payment: Money
    policy_version: str


class DocumentRecord(BaseModel):
    id: UUID
    requested_type: DocumentType
    detected_type: DocumentType
    sha256: str
    is_test_specimen: bool
    fields: dict[str, ExtractedField] = {}
    received_at: datetime


class Validation(BaseModel):
    key: str  # e.g. "income", "name@identification", "address@proof_of_address"
    type: ValidationType
    result: ValidationResult
    origin: ValidationOrigin = ValidationOrigin.system
    detail: dict[str, Any] = {}
    evidence: list[str] = []
    justification: str | None = None
    attempt: int = 1
    policy_version: str
    at: datetime


class Decision(BaseModel):
    kind: Literal["eligibility", "profile", "options", "gate", "rejection", "ok_revocation", "data_correction"]
    result: str
    reason: str | None = None
    actor: Actor
    inputs: dict[str, Any] = {}
    policy_version: str
    at: datetime


class MessageRef(BaseModel):
    id: str
    author: Literal["client", "agent"]
    text: str
    intent: Intent | None = None
    at: datetime


class CaseState(BaseModel):
    client: ClientData = Field(default_factory=ClientData)
    declared: Declared = Field(default_factory=Declared)
    vehicle: Vehicle = Field(default_factory=Vehicle)
    key_quote: KeyQuote | None = None
    profile: Profile | None = None
    options: list[CreditOption] = []
    selected_option_id: str | None = None
    documents: list[DocumentRecord] = []
    validations: dict[str, Validation] = {}
    attempts: dict[str, int] = {}  # ValidationType → non-passed results
    decisions: list[Decision] = []
    messages: list[MessageRef] = []
    open_escalation_id: UUID | None = None


class CaseView(BaseModel):
    id: UUID
    stage: Stage
    status: Status
    version: int
    policy_version: str
    created_at: datetime
    updated_at: datetime
    state: CaseState


class CaseSummary(BaseModel):
    id: UUID
    stage: Stage
    status: Status
    version: int
    updated_at: datetime


class Escalation(BaseModel):
    id: UUID
    case_id: UUID
    reason: EscalationReason
    evidence: dict[str, Any]
    summary: str
    suggested_action: str
    agent_note: str | None = None
    status: Literal["open", "resolved"]
    resolution: dict[str, Any] | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class AuditEntry(BaseModel):
    id: int
    case_id: UUID | None
    at: datetime
    actor: Actor
    on_behalf_of: Literal["client"] | None = None
    tool: str
    stage_before: Stage | None = None
    status_before: Status | None = None
    stage_after: Stage | None = None
    status_after: Status | None = None
    idempotency_key: str
    expected_version: int | None = None
    case_version_after: int | None = None
    outcome: Outcome
    rejection_code: str | None = None
    input: dict[str, Any] = {}
    result: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    policy_version: str | None = None


class MetricsReport(BaseModel):
    vehicle_rejections_by_reason: dict[str, int]
    false_ok_by_reason: dict[str, int]
    mismatches_by_type: dict[str, int]
    cases_with_key_quote: int
    audit_entries: int
