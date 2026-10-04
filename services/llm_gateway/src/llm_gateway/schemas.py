"""Extraction schemas loaded from eval/esquemas.json (R-12)."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

CATEGORY_KEY = {"mensaje": "intencion", "documento": "tipo_documento"}


class Schemas:
    def __init__(self, path: Path):
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.version: int = raw["version"]
        self._entries: dict[str, dict[str, Any]] = {name: raw[name] for name in CATEGORY_KEY}
        self._validators = {name: Draft202012Validator(e["schema"]) for name, e in self._entries.items()}

    def schema(self, name: str) -> dict[str, Any]:
        return self._entries[name]["schema"]

    def rules(self, name: str) -> list[str]:
        return list(self._entries[name].get("reglas", []))

    def field_names(self, name: str) -> list[str]:
        return list(self.schema(name)["properties"]["campos"]["properties"])

    def errors(self, name: str, data: Any) -> list[str]:
        return [e.message for e in self._validators[name].iter_errors(data)]

    def complete(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        """Fill every missing `campos` key with null so sparse fixtures still satisfy the schema."""
        campos = {key: None for key in self.field_names(name)}
        campos.update(data.get("campos") or {})
        return {CATEGORY_KEY[name]: data.get(CATEGORY_KEY[name], "otro"), "campos": campos}

    def fallback(self, name: str) -> dict[str, Any]:
        """Answer of `fake` mode when there is no fixture: category `otro`, every field null (R-11)."""
        return self.complete(name, {CATEGORY_KEY[name]: "otro", "campos": {}})
