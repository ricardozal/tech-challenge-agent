"""Ollama calls with the fixed parameters of Principle V. Only module that imports `ollama`."""

from dataclasses import dataclass
from typing import Any

from ollama import Client

# Same parameters as the model comparison that chose gemma4:12b (eval/).
OPTIONS = {"temperature": 0, "seed": 42, "num_predict": 512}
# OCR has its own budget: a long document must not be cut by the extraction limit.
OCR_OPTIONS = {"temperature": 0, "seed": 42, "num_predict": 1024}
KEEP_ALIVE = "30m"
OCR_PROMPT = "Text Recognition:"


@dataclass
class Completion:
    text: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float | None = None  # set by LlmService around the call


class OllamaClient:
    def __init__(self, url: str, model: str, ocr_model: str, timeout_s: float = 300):
        self.model = model
        self.ocr_model = ocr_model
        self._client = Client(host=url, timeout=timeout_s)

    def chat_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> Completion:
        resp = self._client.chat(
            model=self.model, messages=messages, format=schema, options=OPTIONS, think=False, keep_alive=KEEP_ALIVE
        )
        return Completion(resp.message.content or "", resp.prompt_eval_count, resp.eval_count)

    def chat_text(self, messages: list[dict[str, Any]]) -> Completion:
        resp = self._client.chat(model=self.model, messages=messages, options=OPTIONS, think=False, keep_alive=KEEP_ALIVE)
        return Completion(resp.message.content or "", resp.prompt_eval_count, resp.eval_count)

    def list_models(self) -> list[str]:
        """Installed model names; `name:latest` also counts as `name`."""
        names: list[str] = []
        for m in self._client.list().models:
            name = m.model or ""
            names.append(name)
            if name.endswith(":latest"):
                names.append(name.removesuffix(":latest"))
        return names

    def ocr(self, image: bytes) -> Completion:
        resp = self._client.chat(
            model=self.ocr_model,
            messages=[{"role": "user", "content": OCR_PROMPT, "images": [image]}],
            options=OCR_OPTIONS,
            keep_alive=KEEP_ALIVE,
        )
        return Completion(resp.message.content or "", resp.prompt_eval_count, resp.eval_count)
