"""CORS only for the web origin (specs/002-demo-web research W-04).

The lifespan (database, checkpointer) does not run without the `with` block, so no compose is needed.
"""

import dataclasses
from uuid import uuid4

from fastapi.testclient import TestClient

from agent.config import Settings
from agent.main import create_app

WEB = "http://localhost:8080"


def _preflight(origin: str):
    client = TestClient(create_app(dataclasses.replace(Settings.from_env(), web_origins=(WEB,))))
    return client.options(
        f"/cases/{uuid4()}/messages",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key",
        },
    )


def test_web_origin_is_allowed():
    resp = _preflight(WEB)
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == WEB


def test_other_origin_is_not_allowed():
    assert "access-control-allow-origin" not in _preflight("http://evil.example").headers
