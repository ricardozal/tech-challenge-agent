"""Simulated vehicle registry: liens and reference value (R-15)."""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from actions_api.providers.base import ProviderError, load
from actions_api.rules.text import normalize


@dataclass(frozen=True)
class RegistryRecord:
    lien: bool
    reference_value: Decimal | None


def _key(name: str, make: str, model: str, year: int | str) -> str:
    return "|".join(normalize(part) for part in (name, make, model, year))


class VehicleRegistryProvider:
    def __init__(self, path: Path):
        data = load(path)
        self._records = {_key(r["name"], r["make"], r["model"], r["year"]): r for r in data.get("records", [])}
        self._default = data.get("default", {"lien": False, "reference_value": None})

    def lookup(self, name: str, make: str, model: str, year: int) -> RegistryRecord:
        record = self._records.get(_key(name, make, model, year), self._default)
        if record.get("fail"):
            raise ProviderError("vehicle_registry")
        value = record.get("reference_value")
        return RegistryRecord(lien=bool(record.get("lien")), reference_value=Decimal(str(value)) if value else None)
