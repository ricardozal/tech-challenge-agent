"""Eligibility rule (pure): ownership, liens/debts and spare key (P1)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from actions_api.config import REPO_ROOT
from actions_api.policy import PolicyRegistry
from actions_api.rules.eligibility import Outcome, evaluate
from contracts.case import Vehicle, VehicleRegistry

POLICY = PolicyRegistry.load(REPO_ROOT / "policy").current()
NOW = datetime(2026, 10, 4, tzinfo=UTC)


def vehicle(**overrides) -> Vehicle:
    values = dict(make="Volkswagen", model="Jetta", year=2019, own_name=True, declared_debt=False, spare_key=True)
    values.update(overrides)
    return Vehicle(**values)


def registry(lien=False, value="180000") -> VehicleRegistry:
    return VehicleRegistry(lien=lien, reference_value=Decimal(value) if value else None, checked_at=NOW)


@pytest.mark.req("FR-012")
def test_vehicle_not_in_the_client_name_is_rejected():
    decision = evaluate(vehicle(own_name=False), None, POLICY)
    assert decision.outcome == Outcome.rejected
    assert decision.rejection_reason == "owner_mismatch"
    assert decision.origin == "declared"


@pytest.mark.req("FR-012")
def test_owner_mismatch_is_decisive_even_with_other_answers_pending():
    decision = evaluate(vehicle(own_name=False, declared_debt=None, spare_key=None), None, POLICY)
    assert decision.outcome == Outcome.rejected


@pytest.mark.req("FR-013")
def test_declared_debt_is_rejected_with_declared_origin():
    decision = evaluate(vehicle(declared_debt=True), None, POLICY)
    assert (decision.outcome, decision.rejection_reason, decision.origin) == (Outcome.rejected, "lien_or_debt", "declared")


@pytest.mark.req("FR-013")
def test_registry_lien_is_rejected_with_registry_origin():
    decision = evaluate(vehicle(), registry(lien=True), POLICY)
    assert (decision.outcome, decision.rejection_reason, decision.origin) == (Outcome.rejected, "lien_or_debt", "registry")


@pytest.mark.req("FR-014")
def test_missing_spare_key_is_not_a_rejection_but_needs_a_quote():
    decision = evaluate(vehicle(spare_key=False), registry(), POLICY)
    assert decision.outcome == Outcome.eligible
    assert decision.needs_key_quote is True


def test_eligible_with_spare_key_needs_no_quote():
    decision = evaluate(vehicle(), registry(), POLICY)
    assert decision.outcome == Outcome.eligible and decision.needs_key_quote is False


def test_clean_declaration_still_needs_the_registry():
    assert evaluate(vehicle(), None, POLICY).outcome == Outcome.needs_registry


def test_no_reference_value_is_its_own_outcome():
    assert evaluate(vehicle(), registry(value=None), POLICY).outcome == Outcome.no_reference_value


@pytest.mark.req("FR-015")
@pytest.mark.parametrize("field", ["own_name", "declared_debt", "spare_key", "make", "model", "year"])
def test_unconfirmed_answer_means_no_decision(field):
    decision = evaluate(vehicle(**{field: None}), registry(), POLICY)
    assert decision.outcome == Outcome.incomplete
    assert field in decision.missing
