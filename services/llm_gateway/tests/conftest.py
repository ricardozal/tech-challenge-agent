"""Shared test double for the Ollama client (a dependency of LlmService, not the unit under test)."""

import json
from typing import Any

import pytest

from llm_gateway.ollama_client import Completion

PROMPT_TOKENS, COMPLETION_TOKENS = 812, 64


def _null_answer(schema: dict[str, Any]) -> str:
    """Smallest valid answer for an extraction schema: first category, every field null."""
    props = schema["properties"]
    category = next(k for k in props if k != "campos")
    campos = {k: None for k in props["campos"]["properties"]}
    return json.dumps({category: props[category]["enum"][0], "campos": campos})


class StubOllama:
    """Answers from a per-test queue of texts; `models` may be a list or an exception to raise."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.models: list[str] | Exception = ["gemma4:12b", "glm-ocr"]
        self.calls: list[tuple[str, Any]] = []

    def queue(self, *texts: str) -> "StubOllama":
        self.texts.extend(texts)
        return self

    def _next(self, default: str) -> Completion:
        text = self.texts.pop(0) if self.texts else default
        return Completion(text, PROMPT_TOKENS, COMPLETION_TOKENS)

    def chat_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> Completion:
        self.calls.append(("chat_json", schema))
        return self._next(_null_answer(schema))

    def chat_text(self, messages: list[dict[str, Any]]) -> Completion:
        self.calls.append(("chat_text", messages))
        return self._next("Gracias, sigo con tu solicitud.")

    def ocr(self, image: bytes) -> Completion:
        self.calls.append(("ocr", len(image)))
        return self._next("ESPÉCIMEN DE PRUEBA")

    def list_models(self) -> list[str]:
        if isinstance(self.models, Exception):
            raise self.models
        return list(self.models)


@pytest.fixture
def stub_ollama() -> StubOllama:
    return StubOllama()
