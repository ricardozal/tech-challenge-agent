"""Document validity: identification not expired, proofs not older than N months (FR-030). Pure."""

from datetime import date, datetime

from actions_api.policy_model import Policy
from actions_api.rules.fields import as_date, low_confidence, take, validation
from contracts.case import DocumentRecord, Validation
from contracts.common import DocumentType, ValidationResult, ValidationType


def months_before(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    year, month = divmod(month_index, 12)
    month += 1
    for candidate in (day.day, 30, 29, 28):
        try:
            return date(year, month, candidate)
        except ValueError:
            continue
    raise ValueError(day)


def validate_validity(doc: DocumentRecord, key: str, policy: Policy, today: date, now: datetime) -> Validation:
    vtype = ValidationType.validity
    if doc.detected_type == DocumentType.identification:
        taken = take(doc, ("valid_until",), policy)
        if taken.low:
            return low_confidence(key, vtype, doc, taken.low, policy, now)
        raw = taken.values["valid_until"]
        expires = date(int(raw), 12, 31) if str(raw).isdigit() else as_date(raw)
        if expires is None:
            return low_confidence(key, vtype, doc, ["valid_until"], policy, now)
        ok = expires >= today
        return validation(key, vtype, ValidationResult.passed if ok else ValidationResult.mismatch, doc, policy, now,
                          ["valid_until"], reason=None if ok else "expired", valid_until=expires.isoformat())

    taken = take(doc, (), policy, optional=("issue_date", "period_end"))
    field = "issue_date" if as_date(taken.values.get("issue_date")) else "period_end"
    issued = as_date(taken.values.get(field))
    if issued is None:
        return low_confidence(key, vtype, doc, ["issue_date"], policy, now)
    max_age = policy.documents.max_age_months.get(doc.detected_type, 3)
    cutoff = months_before(today, max_age)
    ok = cutoff <= issued <= today
    return validation(key, vtype, ValidationResult.passed if ok else ValidationResult.mismatch, doc, policy, now,
                      [field], reason=None if ok else "too_old", issued=issued.isoformat(),
                      oldest_accepted=cutoff.isoformat(), max_age_months=max_age)
