"""Simulated providers read YAML fixtures (R-15)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import yaml

T = TypeVar("T")


class ProviderError(RuntimeError):
    """The provider did not answer (simulated with `fail: true`)."""


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def with_retries(call: Callable[[], T], retries: int) -> T:
    """First attempt + `retries` more; re-raises the last ProviderError."""
    last: ProviderError | None = None
    for _ in range(retries + 1):
        try:
            return call()
        except ProviderError as exc:
            last = exc
    assert last is not None
    raise last
