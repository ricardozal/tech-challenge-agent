"""Credit options (P2): one per percentage of the max at the standard term, key financed inside (R-17)."""

from decimal import Decimal

from actions_api.policy_model import Policy
from actions_api.rules.payment import money, monthly_payment
from contracts.case import CreditOption


def build_options(
    max_financeable: Decimal, annual_rate: Decimal, term_months: int, key_cost: Decimal, policy: Policy
) -> list[CreditOption]:
    """An empty list means no viable option (FR-020)."""
    vat = policy.pricing.vat_rate if policy.pricing.apply_vat_on_interest else None
    options = []
    for pct in policy.options.pcts_of_max:
        financed = money(pct * max_financeable)
        client_amount = money(financed - key_cost)
        if client_amount <= 0:
            continue
        options.append(
            CreditOption(
                id=f"opt-{int(pct * 100)}",
                pct_of_max=pct,
                financed_amount=financed,
                key_cost=money(key_cost),
                client_amount=client_amount,
                term_months=term_months,
                annual_rate=annual_rate,
                monthly_payment=monthly_payment(financed, annual_rate, term_months, vat),
                policy_version=policy.policy_version,
            )
        )
    return options
