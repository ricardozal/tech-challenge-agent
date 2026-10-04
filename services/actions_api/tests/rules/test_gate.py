"""Gate rule (pure): every required validation must be passed (FR-036)."""

import pytest

from actions_api.rules.documents import REQUIRED_KEYS
from actions_api.rules.gate import evaluate
from contracts.case import Validation
from tests.support.documents import NOW


def v(key, result="passed", origin="system"):
    return Validation(key=key, type=key.split("@")[0], result=result, origin=origin, policy_version="v", at=NOW)


@pytest.mark.req("FR-036")
def test_passes_only_with_every_required_key_passed():
    validations = {k: v(k) for k in REQUIRED_KEYS}
    assert evaluate(validations).passed is True
    assert evaluate(validations).missing == []


@pytest.mark.req("FR-036")
def test_failed_low_confidence_or_absent_keys_are_missing():
    validations = {k: v(k) for k in REQUIRED_KEYS}
    validations["income"] = v("income", "mismatch")
    validations["name@identification"] = v("name@identification", "low_confidence")
    del validations["vehicle_ownership"]
    decision = evaluate(validations)
    assert decision.passed is False
    assert decision.missing == ["income", "name@identification", "vehicle_ownership"]


@pytest.mark.req("FR-036")
def test_manual_verification_counts_as_passed():
    validations = {k: v(k) for k in REQUIRED_KEYS}
    validations["income"] = v("income", origin="manual")
    assert evaluate(validations).passed is True
