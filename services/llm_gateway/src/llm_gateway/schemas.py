"""Extraction schemas loaded from eval/esquemas.json (R-12), with message schemas per stage (O-13)."""

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from contracts.common import Stage

CATEGORY_KEY = {"mensaje": "intencion", "documento": "tipo_documento"}


class Schemas:
    def __init__(self, path: Path):
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.version: int = raw["version"]
        self._entries: dict[str, dict[str, Any]] = {name: raw[name] for name in CATEGORY_KEY}
        self._stages: dict[str, list[str]] = self._check_stages(raw.get("etapas") or {})
        self._schemas: dict[tuple[str, str | None], dict[str, Any]] = {}
        self._validators: dict[tuple[str, str | None], Draft202012Validator] = {}

    def _check_stages(self, etapas: dict[str, list[str]]) -> dict[str, list[str]]:
        known_stages = {s.value for s in Stage}
        fields = list(self._entries["mensaje"]["schema"]["properties"]["campos"]["properties"])
        for stage, names in etapas.items():
            if stage not in known_stages:
                raise ValueError(f"etapas: {stage!r} is not a Stage value")
            unknown = [n for n in names if n not in fields]
            if unknown:
                raise ValueError(f"etapas.{stage}: unknown fields {unknown}")
            if names != [f for f in fields if f in names]:
                raise ValueError(f"etapas.{stage}: fields must follow the order of the full schema")
        return {stage: list(names) for stage, names in etapas.items()}

    def _key(self, name: str, stage: str | None) -> tuple[str, str | None]:
        """Only `mensaje` has per-stage schemas; a stage without a list uses the full schema."""
        stage = getattr(stage, "value", stage)
        return (name, stage if name == "mensaje" and stage in self._stages else None)

    def stage_fields(self, stage: str) -> list[str]:
        return list(self._stages[stage])

    def schema(self, name: str, stage: str | None = None) -> dict[str, Any]:
        key = self._key(name, stage)
        if key not in self._schemas:
            full = self._entries[name]["schema"]
            if key[1] is None:
                self._schemas[key] = full
            else:
                keep = set(self._stages[key[1]])
                reduced = copy.deepcopy(full)
                campos = reduced["properties"]["campos"]
                campos["properties"] = {k: v for k, v in campos["properties"].items() if k in keep}
                campos["required"] = [k for k in campos["required"] if k in keep]
                self._schemas[key] = reduced
        return self._schemas[key]

    def rules(self, name: str) -> list[str]:
        return list(self._entries[name].get("reglas", []))

    def field_names(self, name: str, stage: str | None = None) -> list[str]:
        return list(self.schema(name, stage)["properties"]["campos"]["properties"])

    def errors(self, name: str, data: Any, stage: str | None = None) -> list[str]:
        key = self._key(name, stage)
        if key not in self._validators:
            self._validators[key] = Draft202012Validator(self.schema(name, stage))
        return [e.message for e in self._validators[key].iter_errors(data)]

    def complete(self, name: str, data: dict[str, Any], stage: str | None = None) -> dict[str, Any]:
        """Fill every missing `campos` key with null so sparse fixtures still satisfy the schema."""
        campos = {key: None for key in self.field_names(name, stage)}
        campos.update(data.get("campos") or {})
        return {CATEGORY_KEY[name]: data.get(CATEGORY_KEY[name], "otro"), "campos": campos}

    def fallback(self, name: str, stage: str | None = None) -> dict[str, Any]:
        """Answer of `fake` mode when there is no fixture: category `otro`, every field null (R-11)."""
        return self.complete(name, {CATEGORY_KEY[name]: "otro", "campos": {}}, stage)
