"""fake / record / ollama (R-11, O-10…O-12).

- fake: answers from fixtures/llm/<task>/<key>.json; without a fixture, `extract` answers category
  `otro` with every field null, `reply` answers a Spanish template, `ocr` fails with fixture_missing.
  Counts which answers were recorded, seeded or missing (GET /v1/fixtures/usage).
- record: calls Ollama and writes the fixture (format v2) to the recording directory; `make record`
  promotes it to fixtures/llm only if its demo reached the expected outcome.
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

from opentelemetry import trace

from contracts.common import Status
from contracts.llm import (
    PROMPT_VERSION,
    ExtractRequest,
    ExtractResponse,
    OcrRequest,
    OcrResponse,
    ReplyRequest,
    ReplyResponse,
    fixture_key,
)
from contracts.redaction import redact
from llm_gateway import prompts
from llm_gateway.ocr_text import first_copy
from llm_gateway.ollama_client import OCR_OPTIONS, OCR_PROMPT, OPTIONS, Completion, OllamaClient
from llm_gateway.redaction import get_logger, log_call
from llm_gateway.schemas import Schemas
from llm_gateway.tracing import TaskTrace, task_span


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
        record_dir: Path | None = None,
        tracer: trace.Tracer | None = None,
    ):
        self.mode = mode
        self.fixtures_dir = fixtures_dir
        self.record_dir = record_dir or fixtures_dir / "_recording"
        self.tracer = tracer or trace.get_tracer("llm_gateway")
        self.schemas = schemas
        self._client_factory = client_factory
        self._client: OllamaClient | None = None
        self.model = model
        self.ocr_model = ocr_model
        self.log = get_logger()
        self.reset_usage()

    # --- fixtures ----------------------------------------------------------------------------

    def _fixture_path(self, task: str, key: str) -> Path:
        return self.fixtures_dir / task / f"{key}.json"

    def load_fixture(self, task: str, key: str) -> dict[str, Any] | None:
        """The whole fixture record (format v2, O-10); a record without `origin` was seeded."""
        path = self._fixture_path(task, key)
        if not path.exists():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        record.setdefault("origin", "seeded")
        return record

    def _save(
        self, task: str, key: str, request: dict[str, Any], response: dict[str, Any], model: str, completion: Completion
    ) -> None:
        """Fixture v2 in the recording directory; metrics are those of the valid attempt (the replayed one)."""
        path = self.record_dir / task / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "request": request,
            "response": response,
            "origin": "recorded",
            "model": model,
            "recorded_at": datetime.now(UTC).isoformat(),
            "schema_version": self.schemas.version,
            "prompt_version": PROMPT_VERSION,
            "latency_ms": completion.latency_ms,
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
        }
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # --- usage of recorded answers (fake only) -------------------------------------------------

    def reset_usage(self) -> None:
        self._counts = {"recorded": 0, "seeded": 0, "missing": 0}
        self._keys: dict[str, dict[str, list[str]]] = {}

    def _count(self, task: str, record: dict[str, Any] | None, key: str) -> None:
        if self.mode != "fake":
            return
        origin = "missing" if record is None else record["origin"]
        self._counts[origin] = self._counts.get(origin, 0) + 1
        keys = self._keys.setdefault(task, {"recorded": [], "seeded": [], "missing": []}).setdefault(origin, [])
        if key not in keys:
            keys.append(key)

    def usage(self) -> dict[str, Any]:
        tasks = {t: {"recorded": [], "seeded": [], "missing": []} for t in ("extract", "ocr", "reply")}
        tasks.update(self._keys)
        return {"mode": self.mode, "counts": dict(self._counts), "by_task": tasks}

    # --- models (ollama / record) --------------------------------------------------------------

    def missing_models(self) -> list[str]:
        """Models this mode needs that Ollama does not have; both if Ollama does not answer (O-15)."""
        wanted = [self.model, self.ocr_model]
        try:
            installed = set(self.client.list_models())
        except Exception:  # noqa: BLE001 - any failure to list means we cannot use the models
            return wanted
        return [m for m in wanted if m not in installed]

    def _timed(self, call: Callable[..., Completion], *args: Any) -> Completion:
        started = time.monotonic()
        completion = call(*args)
        completion.latency_ms = round((time.monotonic() - started) * 1000, 1)
        return completion

    @property
    def client(self) -> OllamaClient:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    # --- tasks -------------------------------------------------------------------------------

    def _replay(self, t: TaskTrace, model: str, messages: list[dict[str, Any]], params: dict[str, Any],
                record: dict[str, Any] | None, output: Any) -> None:
        """LLM span of a fake answer: replay, its origin, and the latency and tokens of the original call."""
        call = t.call(model, messages, params, replay=True,
                      fixture_origin="missing" if record is None else record["origin"],
                      **({"recorded_latency_ms": record["latency_ms"]} if record and record.get("latency_ms") else {}))
        call.done(output, (record or {}).get("prompt_tokens"), (record or {}).get("completion_tokens"),
                  error="fixture_missing" if record is None and output is None else None)

    def extract(self, req: ExtractRequest) -> ExtractResponse:
        started = time.monotonic()
        key = fixture_key("extract", req.schema_name, extract_inputs(req), self.schemas.version)
        stage = getattr(req.stage, "value", req.stage)
        with task_span(self.tracer, "extract", mode=self.mode, schema_name=req.schema_name, stage=stage,
                       schema_version=self.schemas.version, fixture_key=key) as t:
            t.input = req.text
            completion: Completion | None = None
            hit = False
            if self.mode == "fake":
                record = self.load_fixture("extract", key)
                self._count("extract", record, key)
                hit = record is not None
                data = (self.schemas.complete(req.schema_name, record["response"], req.stage) if hit
                        else self.schemas.fallback(req.schema_name, req.stage))
                self._replay(t, self.model, self._extract_prompt(req), dict(OPTIONS, think=False), record, data)
            else:
                data, completion = self._extract_with_model(req, t)
                if self.mode == "record":
                    self._save("extract", key, req.model_dump(mode="json"), data, self.model, completion)
            t.names.append(str((data.get("campos") or {}).get("nombre_completo") or ""))
            t.output = data
            errors = self.schemas.errors(req.schema_name, data, req.stage)
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

    def _extract_prompt(self, req: ExtractRequest) -> list[dict[str, str]]:
        schema = self.schemas.schema(req.schema_name, req.stage)
        return prompts.extract_messages(
            req.schema_name, schema, self.schemas.rules(req.schema_name), req.agent_question, req.text,
        )

    def _extract_with_model(self, req: ExtractRequest, t: TaskTrace) -> tuple[dict[str, Any], Completion]:
        schema = self.schemas.schema(req.schema_name, req.stage)
        messages = self._extract_prompt(req)
        last_error = ""
        for _ in range(2):  # one retry on invalid output; each attempt is its own LLM span
            call = t.call(self.model, messages, dict(OPTIONS, think=False))
            try:
                completion = self._timed(self.client.chat_json, messages, schema)
            except Exception as exc:
                call.done(error=f"{type(exc).__name__}: {exc}")
                raise
            tokens = (completion.prompt_tokens, completion.completion_tokens)
            try:
                data = json.loads(completion.text)
            except json.JSONDecodeError as exc:
                last_error = f"invalid JSON: {exc}"
                call.done(completion.text, *tokens, error=last_error)
                continue
            errors = self.schemas.errors(req.schema_name, data, req.stage)
            if not errors:
                call.done(completion.text, *tokens)
                return data, completion
            last_error = "; ".join(errors[:3])
            call.done(completion.text, *tokens, error=last_error)
        raise InvalidModelOutput(last_error)

    def ocr(self, req: OcrRequest) -> OcrResponse:
        started = time.monotonic()
        content = base64.b64decode(req.content_base64)
        key = fixture_key("ocr", None, ocr_inputs(content), self.schemas.version)
        inputs = {**ocr_inputs(content), "mime_type": req.mime_type}
        # The image never goes into a span; the OCR text is shown (redacted) as input of the extraction.
        messages = [{"role": "user", "content": json.dumps({"prompt": OCR_PROMPT, **inputs})}]
        with task_span(self.tracer, "ocr", mode=self.mode, fixture_key=key) as t:
            t.input = inputs
            completion: Completion | None = None
            hit = False
            if self.mode == "fake":
                record = self.load_fixture("ocr", key)
                self._count("ocr", record, key)
                if record is None:
                    self._replay(t, self.ocr_model, messages, OCR_OPTIONS, None, None)
                    self._log("ocr", started, False, None, "", None)
                    raise FixtureMissing(key)
                text, hit = record["response"]["text"], True
                self._replay(t, self.ocr_model, messages, OCR_OPTIONS, record, {"chars": len(text)})
            else:
                call = t.call(self.ocr_model, messages, OCR_OPTIONS)
                try:
                    completion = self._timed(self.client.ocr, content)
                except Exception as exc:
                    call.done(error=f"{type(exc).__name__}: {exc}")
                    raise
                text = first_copy(completion.text)
                call.done({"chars": len(text)}, completion.prompt_tokens, completion.completion_tokens)
                if self.mode == "record":
                    self._save("ocr", key, ocr_inputs(content), {"text": text}, self.ocr_model, completion)
            t.output = {"chars": len(text)}
        self._log("ocr", started, hit, completion, "", {"chars": len(text)})
        return OcrResponse(text=text, model=self.ocr_model, mode=self.mode, fixture_hit=hit)

    def reply(self, req: ReplyRequest) -> ReplyResponse:
        started = time.monotonic()
        request = req.model_dump(mode="json")
        key = fixture_key("reply", None, request, self.schemas.version)
        names = [req.client_first_name] if req.client_first_name else []
        messages = prompts.reply_messages(req)
        with task_span(self.tracer, "reply", mode=self.mode, stage=request["stage"], fixture_key=key) as t:
            t.input, t.names = request, list(names)
            completion: Completion | None = None
            hit = False
            if self.mode == "fake":
                record = self.load_fixture("reply", key)
                self._count("reply", record, key)
                hit = record is not None
                text = record["response"]["text"] if hit else reply_template(req)
                self._replay(t, self.model, messages, dict(OPTIONS, think=False), record, text)
            else:
                call = t.call(self.model, messages, dict(OPTIONS, think=False))
                try:
                    completion = self._timed(self.client.chat_text, messages)
                except Exception as exc:
                    call.done(error=f"{type(exc).__name__}: {exc}")
                    raise
                text = completion.text.strip()
                call.done(text, completion.prompt_tokens, completion.completion_tokens)
                if self.mode == "record":
                    self._save("reply", key, request, {"text": text}, self.model, completion)
            t.output = text
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
