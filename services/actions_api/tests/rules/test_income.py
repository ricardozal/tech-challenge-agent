"""Income validation (pure): normalize to the same period, compare currency, apply tolerance (FR-027)."""

from decimal import Decimal

import pytest

from actions_api.config import REPO_ROOT
from actions_api.policy import PolicyRegistry
from actions_api.rules.income import to_monthly, validate_income
from contracts.case import Declared
from contracts.common import DocumentType, Periodicity
from tests.support.documents import NOW, doc, payslip

POLICY = PolicyRegistry.load(REPO_ROOT / "policy").current()


def declared(amount="20000", periodicity=Periodicity.monthly, currency="MXN") -> Declared:
    return Declared(employment="employed", income_amount=Decimal(amount), income_periodicity=periodicity,
                    income_currency=currency)


def test_conversions_to_monthly_are_exact():
    assert to_monthly(Decimal("9000"), Periodicity.biweekly) == Decimal("18000")
    assert to_monthly(Decimal("1200"), Periodicity.weekly) == Decimal("5200")
    assert to_monthly(Decimal("20000"), Periodicity.monthly) == Decimal("20000")


@pytest.mark.req("FR-027")
def test_biweekly_proof_is_normalized_before_comparing():
    # declared 20,000 monthly vs 9,000 biweekly = 18,000 monthly: 10% off, still within tolerance
    v = validate_income(declared(), payslip(net=9000), POLICY, NOW)
    assert v.result == "passed" and v.key == "income"
    assert v.detail["declared_monthly"] == "20000.00" and v.detail["proved_monthly"] == "18000.00"
    assert v.policy_version == "2026.10-v1"


@pytest.mark.req("FR-027")
def test_out_of_tolerance_is_a_mismatch():
    v = validate_income(declared(), payslip(net=8000), POLICY, NOW)  # 16,000 monthly = 20% off
    assert v.result == "mismatch" and v.detail["reason"] == "out_of_tolerance"


@pytest.mark.req("FR-027")
def test_declared_weekly_and_proof_biweekly_are_compared_on_the_same_period():
    v = validate_income(declared("5000", Periodicity.weekly), payslip(net=10833.33), POLICY, NOW)
    assert v.result == "passed"  # 21,666.67 vs 21,666.66 monthly


@pytest.mark.req("FR-027")
def test_different_currency_is_a_mismatch():
    v = validate_income(declared(), payslip(net=10000, currency="USD"), POLICY, NOW)
    assert v.result == "mismatch" and v.detail["reason"] == "currency_mismatch"


def test_bank_statement_uses_total_deposits_as_monthly_income():
    statement = doc(DocumentType.bank_statement, full_name="LAURA MÉNDEZ ROJAS", total_deposits=19500, currency="MXN",
                    period_start="2026-09-01", period_end="2026-09-30")
    assert validate_income(declared(), statement, POLICY, NOW).result == "passed"


def test_periodicity_is_derived_from_the_period_when_missing():
    assert validate_income(declared(), payslip(net=10000, periodicity=None), POLICY, NOW).result == "passed"


@pytest.mark.req("FR-033")
def test_low_confidence_amount_is_not_used():
    v = validate_income(declared(), payslip(net=10000) .model_copy(update={"fields": {
        **payslip().fields, "net_income": payslip().fields["net_income"].model_copy(update={"confidence": 0.6})}}),
        POLICY, NOW)
    assert v.result == "low_confidence" and v.detail["fields"] == ["net_income"]
