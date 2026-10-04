"""PII redaction for logs (R-22) and JSON-lines logging."""

import json
import logging
import re
import sys
from typing import Any

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


def get_logger() -> logging.Logger:
    logger = logging.getLogger("llm_gateway")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_call(logger: logging.Logger, record: dict[str, Any]) -> None:
    logger.info(json.dumps(record, ensure_ascii=False, default=str))
