"""Reading extracted document fields under the confidence threshold (FR-033). Pure."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from actions_api.policy_model import Policy
from contracts.case import DocumentRecord, Validation
from contracts.common import ValidationResult, ValidationType


@dataclass
class Taken:
    values: dict[str, Any] = field(default_factory=dict)
    low: list[str] = field(default_factory=list)  # required fields missing or below the threshold


def take(doc: DocumentRecord, required: tuple[str, ...], policy: Policy, optional: tuple[str, ...] = ()) -> Taken:
    """Values usable by a rule. A field below `min_field_confidence` is never used."""
    threshold = float(policy.documents.min_field_confidence)
    taken = Taken()
    for name in (*required, *optional):
        extracted = doc.fields.get(name)
        usable = extracted is not None and extracted.value is not None and extracted.confidence >= threshold
        if usable:
            taken.values[name] = extracted.value
        elif name in required:
            taken.low.append(name)
    return taken


def validation(
    key: str,
    vtype: ValidationType,
    result: ValidationResult,
    doc: DocumentRecord | None,
    policy: Policy,
    now: datetime,
    used: tuple[str, ...] | list[str] = (),
    **detail: Any,
) -> Validation:
    return Validation(
        key=key,
        type=vtype,
        result=result,
        detail=detail,
        evidence=([str(doc.id)] if doc else []) + [f"field:{f}" for f in used],
        policy_version=policy.policy_version,
        at=now,
    )


def low_confidence(key: str, vtype: ValidationType, doc: DocumentRecord, low: list[str], policy: Policy,
                   now: datetime) -> Validation:
    return validation(key, vtype, ValidationResult.low_confidence, doc, policy, now, low, reason="low_confidence",
                      fields=low)


def as_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def as_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None
