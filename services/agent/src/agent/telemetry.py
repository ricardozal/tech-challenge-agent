"""Traces to the local Phoenix console (O-02…O-04). Without PHOENIX_COLLECTOR_ENDPOINT nothing is exported.

The agent starts the trace of each turn itself (span `turn`), so its own FastAPI app is not
instrumented; its outgoing calls carry the context through the instrumented httpx client.
"""

import os

from opentelemetry import trace

PROJECT = "tech-challenge-agent"
_registered = False


def setup() -> None:
    global _registered
    if _registered or not os.environ.get("PHOENIX_COLLECTOR_ENDPOINT"):
        return
    from openinference.instrumentation import TraceConfig
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from phoenix.otel import register

    provider = register(project_name=PROJECT, batch=True, auto_instrument=False, protocol="http/protobuf",
                        verbose=False)
    # Graph nodes show stage, order and duration without the turn state (FR-087, FR-093).
    LangChainInstrumentor().instrument(tracer_provider=provider,
                                       config=TraceConfig(hide_inputs=True, hide_outputs=True))
    HTTPXClientInstrumentor().instrument()
    _registered = True


def tracer() -> trace.Tracer:
    return trace.get_tracer("agent")


def node_span() -> trace.Span | None:
    """Span of the LangGraph node being run, if the LangChain instrumentor is active."""
    if not _registered:
        return None
    from openinference.instrumentation.langchain import get_current_span

    try:
        return get_current_span()
    except Exception:  # noqa: BLE001 - tracing must never break a turn
        return None


# FastAPI >= 0.140 traces requests by itself as soon as a global tracer provider exists. The agent
# starts its own root span per turn, so the app's native telemetry stays off (O-03).
FASTAPI_TELEMETRY_OFF = {"tracing": False, "metrics": False, "logs": False}
