"""Credit profile (P2): bureau score → policy band; max financeable amount (FR-019, FR-020, FR-023)."""

from dataclasses import dataclass
from decimal import Decimal

from actions_api.policy_model import Policy, ProfileBand
from actions_api.rules.payment import money
from contracts.common import Employment


@dataclass(frozen=True)
class ProfileDecision:
    offer: bool
    band: ProfileBand | None = None
    max_financeable: Decimal | None = None
    reason: str | None = None


def assign(score: int, employment: Employment, reference_value: Decimal, policy: Policy) -> ProfileDecision:
    """No offer when the client cannot prove income (no accepted proof) or the score is below every band."""
    if not policy.income.accepted_proofs.get(employment):
        return ProfileDecision(offer=False, reason="no_offer_for_profile")
    bands = sorted(policy.profile_bands, key=lambda b: b.min_score, reverse=True)
    band = next((b for b in bands if score >= b.min_score), None)
    if band is None:
        return ProfileDecision(offer=False, reason="no_offer_for_profile")
    vehicle_share = reference_value * policy.vehicle.max_financeable_pct_of_value
    return ProfileDecision(offer=True, band=band, max_financeable=money(min(band.max_amount, vehicle_share)))
