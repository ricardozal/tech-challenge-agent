"""Name and address matching: normalization + similarity, deterministic (R-18, FR-028, FR-029). Pure."""

import re
from datetime import datetime
from difflib import SequenceMatcher

from actions_api.policy_model import Policy
from actions_api.rules.fields import low_confidence, take, validation
from actions_api.rules.text import normalize
from contracts.case import ClientData, DocumentRecord, Validation
from contracts.common import ValidationResult, ValidationType

ABBREVIATIONS = {
    "AV": "AVENIDA", "AVE": "AVENIDA", "C": "CALLE", "CLL": "CALLE", "COL": "COLONIA", "NO": "NUMERO",
    "NUM": "NUMERO", "BLVD": "BOULEVARD", "CDA": "CERRADA", "PRIV": "PRIVADA", "FRACC": "FRACCIONAMIENTO",
}
# Words that do not tell two addresses apart.
FILLER = {"COLONIA", "NUMERO", "INT", "EXT", "INTERIOR", "EXTERIOR", "CP", "MEX", "MEXICO", "EDO", "ESTADO", "DE",
          "DEL", "LA", "EL", "LOS", "LAS", "Y"}
POSTAL_CODE = re.compile(r"\b\d{5}\b")


def tokens(text: str | None, *, address: bool = False) -> list[str]:
    raw = normalize((text or "").replace("#", " NO "))
    words = [ABBREVIATIONS.get(w, w) for w in raw.split()]
    if address:
        words = [w for w in words if w not in FILLER and not POSTAL_CODE.fullmatch(w)]
    return words


def _token_sort_ratio(a: list[str], b: list[str]) -> float:
    return SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio()


def name_score(a: str | None, b: str | None) -> float:
    return _token_sort_ratio(tokens(a), tokens(b))


def address_score(a: str | None, b: str | None) -> float:
    """Max of token-sort similarity and token containment (one address listing fewer words)."""
    ta, tb = tokens(a, address=True), tokens(b, address=True)
    if not ta or not tb:
        return 0.0
    containment = len(set(ta) & set(tb)) / min(len(set(ta)), len(set(tb)))
    return max(_token_sort_ratio(ta, tb), containment)


def validate_name(client: ClientData, doc: DocumentRecord, key: str, policy: Policy, now: datetime) -> Validation:
    vtype = ValidationType.name
    taken = take(doc, ("full_name",), policy)
    if taken.low:
        return low_confidence(key, vtype, doc, taken.low, policy, now)
    score = name_score(client.full_name, taken.values["full_name"])
    ok = score >= float(policy.matching.name_similarity_threshold)
    return validation(key, vtype, ValidationResult.passed if ok else ValidationResult.mismatch, doc, policy, now,
                      ["full_name"], reason=None if ok else "name_mismatch", score=round(score, 3),
                      threshold=str(policy.matching.name_similarity_threshold))


def validate_address(client: ClientData, doc: DocumentRecord, policy: Policy, now: datetime) -> Validation:
    """Only the proof of address is checked; its holder may be someone else (clarification 2026-10-03)."""
    key, vtype = "address@proof_of_address", ValidationType.address
    taken = take(doc, ("address", "postal_code"), policy)
    if taken.low:
        return low_confidence(key, vtype, doc, taken.low, policy, now)
    if str(taken.values["postal_code"]).strip() != str(client.postal_code or "").strip():
        return validation(key, vtype, ValidationResult.mismatch, doc, policy, now, ["postal_code"],
                          reason="postal_code_mismatch")
    score = address_score(client.address, taken.values["address"])
    ok = score >= float(policy.matching.address_similarity_threshold)
    return validation(key, vtype, ValidationResult.passed if ok else ValidationResult.mismatch, doc, policy, now,
                      ["address", "postal_code"], reason=None if ok else "address_mismatch", score=round(score, 3),
                      threshold=str(policy.matching.address_similarity_threshold))
