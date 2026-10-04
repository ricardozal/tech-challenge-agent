"""Gate "OK para financiera" (FR-036): every required validation passed. Pure."""

from dataclasses import dataclass, field

from actions_api.rules.documents import REQUIRED_KEYS
from contracts.case import Validation
from contracts.common import ValidationResult


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    missing: list[str] = field(default_factory=list)


def evaluate(validations: dict[str, Validation]) -> GateDecision:
    """A manual verification (origin = manual) counts as passed; the decision is still the system's."""
    missing = [k for k in REQUIRED_KEYS if k not in validations or validations[k].result != ValidationResult.passed]
    return GateDecision(passed=not missing, missing=missing)
