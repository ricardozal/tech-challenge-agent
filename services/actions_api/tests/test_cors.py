"""CORS only for the web origin (specs/002-demo-web research W-04).

The lifespan (database) does not run without the `with` block; preflight and /health need no DB.
"""

from datetime import date

from fastapi.testclient import TestClient

from actions_api.config import REPO_ROOT, Settings
from actions_api.main import create_app

WEB = "http://localhost:8080"


def _client(tmp_path) -> TestClient:
    settings = Settings(
        database_url="postgresql://unused@127.0.0.1:9/none",
        policy_dir=REPO_ROOT / "policy",
        providers_dir=REPO_ROOT / "fixtures" / "providers",
        documents_dir=tmp_path / "documents",
        doc_intel_url="http://127.0.0.1:9",
        as_of_date=date(2026, 10, 4),
        web_origins=(WEB,),
    )
    return TestClient(create_app(settings))


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/tools/create_case",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-actor",
        },
    )


def test_web_origin_is_allowed(tmp_path):
    resp = _preflight(_client(tmp_path), WEB)
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == WEB


def test_other_origin_is_not_allowed(tmp_path):
    resp = _preflight(_client(tmp_path), "http://evil.example")
    assert "access-control-allow-origin" not in resp.headers


def test_calls_without_origin_are_unchanged(tmp_path):
    resp = _client(tmp_path).get("/health")
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers
