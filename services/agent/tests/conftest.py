import os

import httpx
import pytest

from tests.support import testdb

AGENT_URL = os.environ.get("AGENT_URL", "http://localhost:8001")
ACTIONS_URL = os.environ.get("ACTIONS_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def test_db():
    if not testdb.available():
        pytest.skip("Postgres not running; run `make up-db`")
    db = testdb.create()
    yield db
    testdb.drop(db)


@pytest.fixture(scope="session")
def stack():
    """Agent tests run against the real compose services (LLM_MODE=fake), no stubs (Principle IX)."""
    for url in (AGENT_URL, ACTIONS_URL):
        try:
            httpx.get(f"{url}/health", timeout=2).raise_for_status()
        except httpx.HTTPError:
            pytest.skip(f"{url} not running; run `make up`")
    with httpx.Client(timeout=120) as http:
        yield {"agent": AGENT_URL, "actions": ACTIONS_URL, "http": http}
