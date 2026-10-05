"""JSON-lines logging of the gateway; the redaction rules live in contracts.redaction (O-09)."""

import json
import logging
import sys
from typing import Any

from contracts.redaction import redact  # noqa: F401 - re-exported for the gateway modules


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
