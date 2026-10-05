"""Traces to the local Phoenix console (O-02). Without PHOENIX_COLLECTOR_ENDPOINT nothing is exported."""

import os

from fastapi import FastAPI

PROJECT = "tech-challenge-agent"
_registered = False
# FastAPI >= 0.140 also traces requests natively; the OpenTelemetry instrumentation below is the one
# used (it extracts the incoming traceparent), so native telemetry stays off to avoid duplicate spans.
FASTAPI_TELEMETRY_OFF = {"tracing": False, "metrics": False, "logs": False}


def setup(app: FastAPI) -> None:
    global _registered
    if not os.environ.get("PHOENIX_COLLECTOR_ENDPOINT"):
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from phoenix.otel import register

    if not _registered:
        # batch=True exports in the background: a Phoenix that is down never slows a request (FR-092).
        register(project_name=PROJECT, batch=True, auto_instrument=True, protocol="http/protobuf", verbose=False)
        HTTPXClientInstrumentor().instrument()
        _registered = True
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health", exclude_spans=["receive", "send"])
