"""PII redaction shared by logs and traces (R-22, O-09): CURP, RFC, phone numbers and known names."""

import re

CURP = re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b", re.IGNORECASE)
RFC = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b", re.IGNORECASE)
PHONE = re.compile(r"(?<!\d)(?:\+?52[\s-]?)?(?:\d[\s-]?){9}\d(?!\d)")


def redact(text: str, names: list[str] | None = None) -> str:
    text = CURP.sub("[REDACTED_CURP]", text)
    text = RFC.sub("[REDACTED_RFC]", text)
    text = PHONE.sub("[REDACTED_PHONE]", text)
    for name in names or []:
        for token in {t for t in re.split(r"\s+", name or "") if len(t) >= 3}:
            text = re.sub(rf"\b{re.escape(token)}\b", "[REDACTED_NAME]", text, flags=re.IGNORECASE)
    return text
