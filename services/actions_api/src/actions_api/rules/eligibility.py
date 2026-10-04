"""Vehicle eligibility (P1): ownership, liens or debts, spare key. Pure function (Principle II)."""

from dataclasses import dataclass, field
from enum import StrEnum

from actions_api.policy_model import Policy
from contracts.case import Vehicle, VehicleRegistry

REQUIRED = ("make", "model", "year", "own_name", "declared_debt", "spare_key")


class Outcome(StrEnum):
    eligible = "eligible"
    rejected = "rejected"
    incomplete = "incomplete"  # some answer is not confirmed yet (FR-015)
    needs_registry = "needs_registry"  # clean declaration; the registry decides
    no_reference_value = "no_reference_value"


@dataclass(frozen=True)
class EligibilityDecision:
    outcome: Outcome
    rejection_reason: str | None = None
    origin: str | None = None  # "declared" | "registry"
    needs_key_quote: bool = False
    missing: list[str] = field(default_factory=list)


def evaluate(vehicle: Vehicle, registry: VehicleRegistry | None, policy: Policy) -> EligibilityDecision:
    """A confirmed disqualifier decides on its own; otherwise every answer must be confirmed.

    `policy` is part of the signature like every rule (Principle VI); eligibility has no thresholds
    in policy 2026.10-v1.
    """
    del policy
    if vehicle.own_name is False:
        return EligibilityDecision(Outcome.rejected, "owner_mismatch", "declared")
    if vehicle.declared_debt is True:
        return EligibilityDecision(Outcome.rejected, "lien_or_debt", "declared")

    missing = [name for name in REQUIRED if getattr(vehicle, name) is None]
    if missing:
        return EligibilityDecision(Outcome.incomplete, missing=missing)
    if registry is None:
        return EligibilityDecision(Outcome.needs_registry)
    if registry.lien:
        return EligibilityDecision(Outcome.rejected, "lien_or_debt", "registry")
    if registry.reference_value is None:
        return EligibilityDecision(Outcome.no_reference_value)
    return EligibilityDecision(Outcome.eligible, needs_key_quote=vehicle.spare_key is False)
