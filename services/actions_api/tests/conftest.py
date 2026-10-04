import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from actions_api.config import REPO_ROOT, Settings
from actions_api.main import create_app
from tests.support import testdb


@pytest.fixture(scope="session")
def test_db():
    if not testdb.available():
        pytest.skip("Postgres not running; run `make up-db`")
    db = testdb.create()
    yield db
    testdb.drop(db)


def make_settings(test_db, tmp_path: Path, **overrides: Any) -> Settings:
    values = dict(
        database_url=test_db.actions_url,
        policy_dir=REPO_ROOT / "policy",
        providers_dir=REPO_ROOT / "fixtures" / "providers",
        documents_dir=tmp_path / "documents",
        doc_intel_url="http://127.0.0.1:9",
        as_of_date=date(2026, 10, 4),
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def client(test_db, tmp_path):
    with TestClient(create_app(make_settings(test_db, tmp_path))) as c:
        yield c


class Api:
    """Small helper to call tools the way the agent and the advisor do."""

    def __init__(self, client: TestClient):
        self.client = client

    def call(self, tool: str, case_id=None, version=None, *, actor="agent", key=None, input=None, **context):
        body = {
            "context": {
                "case_id": str(case_id) if case_id else None,
                "idempotency_key": key or f"k-{uuid.uuid4().hex}",
                "expected_version": version,
                **context,
            },
            "input": input or {},
        }
        return self.client.post(f"/tools/{tool}", json=body, headers={"X-Actor": actor})

    def create_case(self) -> dict:
        resp = self.call("create_case")
        assert resp.status_code == 200, resp.text
        return resp.json()["case"]

    def case(self, case_id) -> dict:
        return self.client.get(f"/cases/{case_id}").json()

    def audit(self, case_id) -> list[dict]:
        return self.client.get(f"/cases/{case_id}/audit").json()


@pytest.fixture
def api(client) -> Api:
    return Api(client)
