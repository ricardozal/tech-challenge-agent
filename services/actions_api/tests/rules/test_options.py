"""Credit options: percentages of the max at the standard term, key cost included (P2)."""

from decimal import Decimal

import pytest

from actions_api.config import REPO_ROOT
from actions_api.policy import PolicyRegistry
from actions_api.rules.options import build_options

POLICY = PolicyRegistry.load(REPO_ROOT / "policy").current()


def options(max_financeable="90000", key_cost="0", rate="0.24", term=24):
    return build_options(Decimal(max_financeable), Decimal(rate), term, Decimal(key_cost), POLICY)


@pytest.mark.req("FR-021")
def test_one_option_per_percentage_at_the_standard_term():
    opts = options()
    assert [o.id for o in opts] == ["opt-100", "opt-75", "opt-50"]
    assert [o.financed_amount for o in opts] == [Decimal("90000.00"), Decimal("67500.00"), Decimal("45000.00")]
    assert {o.term_months for o in opts} == {24} and {o.annual_rate for o in opts} == {Decimal("0.24")}
    assert [o.monthly_payment for o in opts] == [Decimal("4932.63"), Decimal("3699.47"), Decimal("2466.31")]
    assert {o.policy_version for o in opts} == {"2026.10-v1"}


@pytest.mark.req("FR-022")
def test_key_cost_is_financed_inside_each_option():
    opts = options(key_cost="1850.00")
    first = opts[0]
    assert first.financed_amount == Decimal("90000.00")
    assert first.key_cost == Decimal("1850.00")
    assert first.client_amount == Decimal("88150.00")
    assert first.monthly_payment == Decimal("4932.63")  # the payment covers the key


@pytest.mark.req("FR-022")
def test_option_is_skipped_when_the_key_eats_the_whole_amount():
    opts = options(max_financeable="4000", key_cost="3200")
    assert [o.id for o in opts] == ["opt-100"]  # 3,000 and 2,000 financed are below the 3,200 key


@pytest.mark.req("FR-020")
def test_no_option_left_means_no_offer():
    assert options(max_financeable="2000", key_cost="2500") == []


@pytest.mark.req("FR-023")
def test_financed_total_never_exceeds_the_max():
    assert all(o.financed_amount <= Decimal("90000") for o in options(key_cost="1850"))
