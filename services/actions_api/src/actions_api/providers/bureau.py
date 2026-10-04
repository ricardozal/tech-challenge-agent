"""Simulated credit bureau: score by declared full name (R-15)."""

from pathlib import Path

from actions_api.providers.base import ProviderError, load
from actions_api.rules.text import normalize


class BureauProvider:
    def __init__(self, path: Path):
        data = load(path)
        self._records = {normalize(r["name"]): r for r in data.get("records", [])}
        self._default = data["default"]

    def score(self, full_name: str) -> int:
        record = self._records.get(normalize(full_name), self._default)
        if record.get("fail"):
            raise ProviderError("bureau")
        return int(record["score"])
