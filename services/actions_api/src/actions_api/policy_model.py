"""Policy model (pure data, no I/O); rules receive it as a parameter (Principle VI)."""

from decimal import Decimal

from pydantic import BaseModel

from contracts.common import DocumentType, Employment


class ProfileBand(BaseModel):
    band: str
    min_score: int
    max_amount: Decimal
    annual_rate: Decimal
    standard_term_months: int


class VehiclePolicy(BaseModel):
    max_financeable_pct_of_value: Decimal


class OptionsPolicy(BaseModel):
    pcts_of_max: list[Decimal]


class PricingPolicy(BaseModel):
    apply_vat_on_interest: bool
    vat_rate: Decimal


class IncomePolicy(BaseModel):
    tolerance_pct: Decimal
    expected_currency: str
    accepted_proofs: dict[Employment, list[DocumentType]]


class DocumentsPolicy(BaseModel):
    min_field_confidence: Decimal
    max_age_months: dict[DocumentType, int]


class MatchingPolicy(BaseModel):
    name_similarity_threshold: Decimal
    address_similarity_threshold: Decimal


class EscalationPolicy(BaseModel):
    max_correction_attempts: int
    provider_retries: int


class Policy(BaseModel):
    policy_version: str
    profile_bands: list[ProfileBand]
    vehicle: VehiclePolicy
    options: OptionsPolicy
    pricing: PricingPolicy
    income: IncomePolicy
    documents: DocumentsPolicy
    matching: MatchingPolicy
    escalation: EscalationPolicy
