"""Shared redaction policy for logs and traces (R-22, O-09, FR-093)."""

import pytest

from contracts.redaction import redact


@pytest.mark.req("FR-093")
def test_redaction_removes_curp_rfc_phones_and_known_names():
    text = "Soy Laura Méndez, CURP MERL880412MMCNJR09, RFC MERL880412AB1, tel 55 1234 5678"
    out = redact(text, ["Laura Méndez Rojas"])
    for secret in ("MERL880412MMCNJR09", "MERL880412AB1", "5678", "Laura", "Méndez"):
        assert secret not in out
    assert "[REDACTED_CURP]" in out and "[REDACTED_RFC]" in out and "[REDACTED_PHONE]" in out
