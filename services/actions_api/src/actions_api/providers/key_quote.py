"""Simulated spare-key quote (R-15)."""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from actions_api.providers.base import ProviderError, load
from actions_api.rules.text import normalize


@dataclass(frozen=True)
class Quote:
    amount: Decimal
    quote_id: str


def _key(make: str, model: str, year: int | str) -> str:
    return "|".join(normalize(part) for part in (make, model, year))


class KeyQuoteProvider:
    def __init__(self, path: Path):
        data = load(path)
        self._records = {_key(r["make"], r["model"], r["year"]): r for r in data.get("records", [])}
        self._default = data["default"]

    def quote(self, make: str, model: str, year: int) -> Quote:
        record = self._records.get(_key(make, model, year), self._default)
        if record.get("fail"):
            raise ProviderError("key_quote")
        return Quote(amount=Decimal(str(record["amount"])), quote_id=str(record["quote_id"]))
