"""French amortization with VAT on interest (R-17); expected values computed independently."""

from decimal import Decimal

import pytest

from actions_api.rules.payment import monthly_payment


@pytest.mark.parametrize(
    ("principal", "rate", "term", "expected"),
    [("90000", "0.24", 24, "4932.63"), ("67500", "0.24", 24, "3699.47"), ("45000", "0.24", 24, "2466.31"),
     ("100000", "0.32", 24, "5964.27"), ("60000", "0.42", 18, "4762.74")],
)
def test_payment_matches_hand_computed_values_to_the_cent(principal, rate, term, expected):
    assert monthly_payment(Decimal(principal), Decimal(rate), term, Decimal("0.16")) == Decimal(expected)


def test_without_vat_and_zero_rate():
    assert monthly_payment(Decimal("12000"), Decimal("0"), 12, None) == Decimal("1000.00")
    assert monthly_payment(Decimal("90000"), Decimal("0.24"), 24, None) < Decimal("4932.63")
