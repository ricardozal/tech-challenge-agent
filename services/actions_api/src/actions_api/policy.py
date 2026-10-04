"""Versioned business policy (R-14): policy/policy.yaml is current, policy/archive/*.yaml are older."""

from decimal import Decimal
from pathlib import Path

import yaml
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


class PolicyUnavailable(LookupError):
    pass


class PolicyRegistry:
    def __init__(self, current: Policy, by_version: dict[str, Policy]):
        self._current = current
        self._by_version = by_version

    @classmethod
    def load(cls, policy_dir: Path) -> "PolicyRegistry":
        current = _read(policy_dir / "policy.yaml")
        by_version = {current.policy_version: current}
        for path in sorted((policy_dir / "archive").glob("*.yaml")):
            archived = _read(path)
            by_version.setdefault(archived.policy_version, archived)
        return cls(current, by_version)

    def current(self) -> Policy:
        return self._current

    def get(self, version: str) -> Policy:
        try:
            return self._by_version[version]
        except KeyError:
            raise PolicyUnavailable(version) from None

    def versions(self) -> list[str]:
        return sorted(self._by_version)


def _read(path: Path) -> Policy:
    with path.open(encoding="utf-8") as fh:
        return Policy.model_validate(yaml.safe_load(fh))
