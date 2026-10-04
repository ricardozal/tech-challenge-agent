"""Income: proved vs declared on the same period, same currency, within tolerance (FR-027). Pure."""

from datetime import datetime
from decimal import Decimal

from actions_api.policy_model import Policy
from actions_api.rules.fields import as_date, as_decimal, low_confidence, take, validation
from actions_api.rules.payment import money
from contracts.case import Declared, DocumentRecord, Validation
from contracts.common import DocumentType, Periodicity, ValidationResult, ValidationType

KEY = "income"
PER_MONTH = {Periodicity.weekly: Decimal(52) / Decimal(12), Periodicity.biweekly: Decimal(2), Periodicity.monthly: Decimal(1)}


def to_monthly(amount: Decimal, periodicity: Periodicity) -> Decimal:
    return amount * PER_MONTH[periodicity]


def _periodicity_from_dates(start: str | None, end: str | None) -> Periodicity | None:
    first, last = as_date(start), as_date(end)
    if not first or not last or last < first:
        return None
    days = (last - first).days + 1
    return Periodicity.weekly if days <= 8 else Periodicity.biweekly if days <= 16 else Periodicity.monthly


def validate_income(declared: Declared, doc: DocumentRecord, policy: Policy, now: datetime) -> Validation:
    vtype = ValidationType.income
    if doc.detected_type == DocumentType.bank_statement:
        taken = take(doc, ("total_deposits",), policy, optional=("currency",))
        amount_field, periodicity = "total_deposits", Periodicity.monthly
    else:
        taken = take(doc, ("net_income",), policy, optional=("currency", "periodicity", "period_start", "period_end"))
        amount_field = "net_income"
        raw = taken.values.get("periodicity")
        periodicity = Periodicity(raw) if raw in Periodicity.__members__ else _periodicity_from_dates(
            taken.values.get("period_start"), taken.values.get("period_end")
        )
        if periodicity is None:
            taken.low.append("periodicity")
    if taken.low:
        return low_confidence(KEY, vtype, doc, taken.low, policy, now)

    proved = as_decimal(taken.values[amount_field])
    if proved is None or proved <= 0:
        return low_confidence(KEY, vtype, doc, [amount_field], policy, now)

    proof_currency = str(taken.values.get("currency") or policy.income.expected_currency).upper()
    if proof_currency != declared.income_currency.upper():
        return validation(KEY, vtype, ValidationResult.mismatch, doc, policy, now, [amount_field, "currency"],
                          reason="currency_mismatch", declared_currency=declared.income_currency,
                          proof_currency=proof_currency)

    declared_monthly = to_monthly(declared.income_amount, declared.income_periodicity)
    proved_monthly = to_monthly(proved, periodicity)
    diff = abs(proved_monthly - declared_monthly) / declared_monthly
    within = diff <= policy.income.tolerance_pct
    return validation(
        KEY, vtype, ValidationResult.passed if within else ValidationResult.mismatch, doc, policy, now,
        [amount_field],
        reason=None if within else "out_of_tolerance",
        declared_monthly=str(money(declared_monthly)),
        proved_monthly=str(money(proved_monthly)),
        difference_pct=str(money(diff * 100)),
        tolerance_pct=str(money(policy.income.tolerance_pct * 100)),
        proof_periodicity=periodicity.value,
    )
