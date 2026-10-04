"""Profile rule (pure): bureau score → band, no offer, max financeable (P2)."""

from decimal import Decimal

import pytest

from actions_api.config import REPO_ROOT
from actions_api.policy import PolicyRegistry
from actions_api.rules.profile import assign
from contracts.common import Employment

POLICY = PolicyRegistry.load(REPO_ROOT / "policy").current()
VALUE = Decimal("180000")


@pytest.mark.req("FR-019")
@pytest.mark.parametrize(
    ("score", "band", "max_amount", "rate", "term"),
    [(720, "A", "150000", "0.24", 24), (700, "A", "150000", "0.24", 24), (650, "B", "100000", "0.32", 24),
     (550, "C", "60000", "0.42", 18)],
)
def test_score_maps_to_the_policy_band(score, band, max_amount, rate, term):
    decision = assign(score, Employment.employed, Decimal("900000"), POLICY)
    assert decision.offer and decision.band.band == band
    assert decision.band.max_amount == Decimal(max_amount)
    assert decision.band.annual_rate == Decimal(rate)
    assert decision.band.standard_term_months == term


@pytest.mark.req("FR-020")
def test_score_below_the_lowest_band_has_no_offer():
    decision = assign(549, Employment.employed, VALUE, POLICY)
    assert not decision.offer and decision.reason == "no_offer_for_profile"


@pytest.mark.req("FR-020")
def test_unemployed_has_no_offer():
    decision = assign(800, Employment.unemployed, VALUE, POLICY)
    assert not decision.offer and decision.reason == "no_offer_for_profile"


@pytest.mark.req("FR-023")
def test_max_financeable_is_the_lower_of_band_limit_and_vehicle_share():
    # band A allows 150,000 but 50% of a 180,000 car is 90,000
    assert assign(720, Employment.employed, VALUE, POLICY).max_financeable == Decimal("90000.00")
    # band C allows 60,000 and 50% of the car is 90,000
    assert assign(560, Employment.employed, VALUE, POLICY).max_financeable == Decimal("60000.00")


@pytest.mark.req("FR-047")
def test_changing_a_threshold_in_the_policy_changes_the_result():
    stricter = POLICY.model_copy(deep=True)
    stricter.vehicle.max_financeable_pct_of_value = Decimal("0.30")
    stricter.profile_bands[0].min_score = 750
    decision = assign(720, Employment.employed, VALUE, stricter)
    assert decision.band.band == "B"
    assert decision.max_financeable == Decimal("54000.00")
