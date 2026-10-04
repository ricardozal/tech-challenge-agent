"""Monthly payment: French amortization, VAT on interest, Decimal rounded to cents (R-17)."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def monthly_payment(principal: Decimal, annual_rate: Decimal, term_months: int, vat_rate: Decimal | None) -> Decimal:
    rate = annual_rate / 12
    if vat_rate is not None:
        rate *= 1 + vat_rate
    if rate == 0:
        return money(principal / term_months)
    return money(principal * rate / (1 - (1 + rate) ** -term_months))
