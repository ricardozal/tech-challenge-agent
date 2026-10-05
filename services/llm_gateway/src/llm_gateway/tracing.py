"""Spans of the gateway (contracts/tracing.md, O-07): one CHAIN span per task and one LLM span per call.

LLM spans are written when the task ends, with the real start and end times of each call, so that
inputs and outputs are redacted with the names the task learned (e.g. `nombre_completo` of the
extraction) — the same policy as the logs (contracts.redaction, FR-093).
"""

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from openinference.semconv.trace import MessageAttributes, OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from contracts.redaction import redact


def _json(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)


@dataclass
class Call:
    """One call to the model (or one replay of a recorded answer)."""

    model: str
    messages: list[dict[str, Any]]
    params: dict[str, Any]
    attempt: int
    start_ns: int = field(default_factory=time.time_ns)
    end_ns: int | None = None
    output: Any = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def done(self, output: Any = None, prompt_tokens: int | None = None, completion_tokens: int | None = None,
             error: str | None = None) -> None:
        self.end_ns = time.time_ns()
        self.output, self.prompt_tokens, self.completion_tokens, self.error = output, prompt_tokens, completion_tokens, error


@dataclass
class TaskTrace:
    task: str
    metadata: dict[str, Any]
    input: Any = None
    output: Any = None
    names: list[str] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    error: str | None = None

    def call(self, model: str, messages: list[dict[str, Any]], params: dict[str, Any], **metadata: Any) -> Call:
        call = Call(model, messages, params, attempt=len(self.calls) + 1, metadata=metadata)
        self.calls.append(call)
        return call


def _set_messages(span: Span, prefix: str, messages: list[dict[str, Any]], names: list[str]) -> None:
    for i, message in enumerate(messages):
        span.set_attribute(f"{prefix}.{i}.{MessageAttributes.MESSAGE_ROLE}", message.get("role", ""))
        span.set_attribute(f"{prefix}.{i}.{MessageAttributes.MESSAGE_CONTENT}",
                           redact(str(message.get("content", "")), names))


def _emit_call(tracer: trace.Tracer, parent: Span, call: Call, names: list[str]) -> None:
    span = tracer.start_span(call.model, context=trace.set_span_in_context(parent), start_time=call.start_ns)
    span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.LLM.value)
    span.set_attribute(SpanAttributes.LLM_PROVIDER, "ollama")
    span.set_attribute(SpanAttributes.LLM_MODEL_NAME, call.model)
    span.set_attribute(SpanAttributes.LLM_INVOCATION_PARAMETERS, _json(call.params))
    user = next((m["content"] for m in reversed(call.messages) if m.get("role") == "user"), "")
    span.set_attribute(SpanAttributes.INPUT_VALUE, redact(str(user), names))
    _set_messages(span, SpanAttributes.LLM_INPUT_MESSAGES, call.messages, names)
    if call.output is not None:
        out = redact(_json(call.output), names)
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, out)
        _set_messages(span, SpanAttributes.LLM_OUTPUT_MESSAGES, [{"role": "assistant", "content": out}], names)
    if call.prompt_tokens is not None:
        span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_PROMPT, call.prompt_tokens)
    if call.completion_tokens is not None:
        span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_COMPLETION, call.completion_tokens)
    if call.prompt_tokens is not None and call.completion_tokens is not None:
        span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_TOTAL, call.prompt_tokens + call.completion_tokens)
    span.set_attribute(SpanAttributes.METADATA, _json({"attempt": call.attempt, **call.metadata}))
    if call.error:
        span.set_status(Status(StatusCode.ERROR, call.error))
    span.end(end_time=call.end_ns or time.time_ns())


@contextmanager
def task_span(tracer: trace.Tracer, task: str, **metadata: Any) -> Iterator[TaskTrace]:
    """CHAIN span of a gateway task; an exception marks it ERROR and is re-raised."""
    trace_ = TaskTrace(task, {"task": task, **metadata})
    with tracer.start_as_current_span(task, record_exception=False, set_status_on_exception=False) as span:
        try:
            yield trace_
        except Exception as exc:
            trace_.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            names = [n for n in trace_.names if n]
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
            span.set_attribute(SpanAttributes.METADATA, _json(trace_.metadata))
            if trace_.input is not None:
                span.set_attribute(SpanAttributes.INPUT_VALUE, redact(_json(trace_.input), names))
            if trace_.output is not None:
                span.set_attribute(SpanAttributes.OUTPUT_VALUE, redact(_json(trace_.output), names))
            if trace_.error:
                span.set_status(Status(StatusCode.ERROR, trace_.error))
            for call in trace_.calls:
                _emit_call(tracer, span, call, names)
