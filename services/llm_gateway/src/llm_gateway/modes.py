"""fake / record / ollama (R-11).

- fake: answers from fixtures/llm/<task>/<key>.json; without a fixture, `extract` answers category
  `otro` with every field null, `reply` answers a Spanish template, `ocr` fails with fixture_missing.
- record: calls Ollama and writes the fixture.
- ollama: calls Ollama.
"""

import base64
import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contracts.common import Status
from contracts.llm import (
    ExtractRequest,
    ExtractResponse,
    OcrRequest,
    OcrResponse,
    ReplyRequest,
    ReplyResponse,
    fixture_key,
)
from llm_gateway import prompts
from llm_gateway.ollama_client import Completion, OllamaClient
from llm_gateway.redaction import get_logger, log_call, redact
from llm_gateway.schemas import Schemas


class FixtureMissing(LookupError):
    pass


class InvalidModelOutput(ValueError):
    pass


REPLY_TEMPLATES = {
    Status.escalated: "Un asesor revisará tu caso y se pondrá en contacto contigo.",
    Status.ok_for_lender: "¡Listo! Tu caso quedó completo y pasa a revisión de la financiera.",
    Status.rejected: "Lo siento, por ahora no podemos continuar con tu solicitud.",
    Status.cancelled: "Tu solicitud quedó cancelada. Si cambias de opinión, aquí estaré.",
}


def reply_template(req: ReplyRequest) -> str:
    parts: list[str] = []
    if req.status != Status.active:
        parts.append(REPLY_TEMPLATES[req.status])
        reason = req.facts.get("reason_es") if isinstance(req.facts, dict) else None
        if reason:
            parts.append(f"Motivo: {reason}.")
    note = req.facts.get("note_es") if isinstance(req.facts, dict) else None
    if note:
        parts.append(str(note))
    if req.next_question:
        parts.append(req.next_question)
    return " ".join(parts) or "Gracias, sigo con tu solicitud."


def extract_inputs(req: ExtractRequest) -> dict[str, Any]:
    return {"stage": req.stage, "agent_question": req.agent_question, "text": req.text}


def ocr_inputs(content: bytes) -> dict[str, Any]:
    return {"sha256": hashlib.sha256(content).hexdigest()}


class LlmService:
    def __init__(
        self,
        mode: str,
        fixtures_dir: Path,
        schemas: Schemas,
        client_factory: Callable[[], OllamaClient],
        model: str,
        ocr_model: str,
    ):
        self.mode = mode
        self.fixtures_dir = fixtures_dir
        self.schemas = schemas
        self._client_factory = client_factory
        self._client: OllamaClient | None = None
        self.model = model
        self.ocr_model = ocr_model
        self.log = get_logger()

    # --- fixtures ----------------------------------------------------------------------------

    def _fixture_path(self, task: str, key: str) -> Path:
        return self.fixtures_dir / task / f"{key}.json"

    def _load(self, task: str, key: str) -> dict[str, Any] | None:
        path = self._fixture_path(task, key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["response"]

    def _save(self, task: str, key: str, request: dict[str, Any], response: dict[str, Any], model: str) -> None:
        path = self._fixture_path(task, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"request": request, "response": response, "recorded_at": datetime.now(UTC).isoformat(), "model": model}
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @property
    def client(self) -> OllamaClient:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    # --- tasks -------------------------------------------------------------------------------

    def extract(self, req: ExtractRequest) -> ExtractResponse:
        started = time.monotonic()
        key = fixture_key("extract", req.schema_name, extract_inputs(req))
        completion: Completion | None = None
        hit = False
        if self.mode == "fake":
            stored = self._load("extract", key)
            hit = stored is not None
            data = self.schemas.complete(req.schema_name, stored) if hit else self.schemas.fallback(req.schema_name)
        else:
            data, completion = self._extract_with_model(req)
            if self.mode == "record":
                self._save("extract", key, req.model_dump(mode="json"), data, self.model)
        errors = self.schemas.errors(req.schema_name, data)
        if errors:
            raise InvalidModelOutput("; ".join(errors[:3]))
        self._log("extract", started, hit, completion, req.text, data)
        return ExtractResponse(
            data=data,
            schema_name=req.schema_name,
            schema_version=self.schemas.version,
            model=self.model,
            mode=self.mode,
            fixture_hit=hit,
        )

    def _extract_with_model(self, req: ExtractRequest) -> tuple[dict[str, Any], Completion]:
        messages = prompts.extract_messages(
            req.schema_name, self.schemas.rules(req.schema_name), req.stage, req.agent_question, req.text
        )
        last_error = ""
        for _ in range(2):  # one retry on invalid output
            completion = self.client.chat_json(messages, self.schemas.schema(req.schema_name))
            try:
                data = json.loads(completion.text)
            except json.JSONDecodeError as exc:
                last_error = f"invalid JSON: {exc}"
                continue
            errors = self.schemas.errors(req.schema_name, data)
            if not errors:
                return data, completion
            last_error = "; ".join(errors[:3])
        raise InvalidModelOutput(last_error)

    def ocr(self, req: OcrRequest) -> OcrResponse:
        started = time.monotonic()
        content = base64.b64decode(req.content_base64)
        key = fixture_key("ocr", None, ocr_inputs(content))
        completion: Completion | None = None
        hit = False
        if self.mode == "fake":
            stored = self._load("ocr", key)
            if stored is None:
                self._log("ocr", started, False, None, "", None)
                raise FixtureMissing(key)
            text, hit = stored["text"], True
        else:
            completion = self.client.ocr(content)
            text = completion.text
            if self.mode == "record":
                self._save("ocr", key, ocr_inputs(content), {"text": text}, self.ocr_model)
        self._log("ocr", started, hit, completion, "", {"chars": len(text)})
        return OcrResponse(text=text, model=self.ocr_model, mode=self.mode, fixture_hit=hit)

    def reply(self, req: ReplyRequest) -> ReplyResponse:
        started = time.monotonic()
        request = req.model_dump(mode="json")
        key = fixture_key("reply", None, request)
        completion: Completion | None = None
        hit = False
        if self.mode == "fake":
            stored = self._load("reply", key)
            hit = stored is not None
            text = stored["text"] if hit else reply_template(req)
        else:
            completion = self.client.chat_text(prompts.reply_messages(req))
            text = completion.text.strip()
            if self.mode == "record":
                self._save("reply", key, request, {"text": text}, self.model)
        names = [req.client_first_name] if req.client_first_name else []
        self._log("reply", started, hit, completion, json.dumps(request, ensure_ascii=False), {"text": text}, names)
        return ReplyResponse(text=text, model=self.model, mode=self.mode, fixture_hit=hit)

    # --- logging -----------------------------------------------------------------------------

    def _log(
        self,
        task: str,
        started: float,
        hit: bool,
        completion: Completion | None,
        input_text: str,
        output: Any,
        names: list[str] | None = None,
    ) -> None:
        names = list(names or [])
        if isinstance(output, dict):
            campos = output.get("campos") or {}
            if campos.get("nombre_completo"):
                names.append(str(campos["nombre_completo"]))
        log_call(
            self.log,
            {
                "task": task,
                "model": self.ocr_model if task == "ocr" else self.model,
                "mode": self.mode,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
                "prompt_tokens": completion.prompt_tokens if completion else None,
                "completion_tokens": completion.completion_tokens if completion else None,
                "fixture_hit": hit,
                "fixture_miss": self.mode == "fake" and not hit,
                "input": redact(input_text[:500], names),
                "output": redact(json.dumps(output, ensure_ascii=False, default=str)[:500], names),
            },
        )
