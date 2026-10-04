"""Shared settings for cross-service tests (architecture and e2e)."""

import os

import httpx
import pytest

ACTIONS_URL = os.environ.get("ACTIONS_URL", "http://localhost:8000")
AGENT_URL = os.environ.get("AGENT_URL", "http://localhost:8001")
LLM_URL = os.environ.get("LLM_URL", "http://localhost:8002")
DOC_INTEL_URL = os.environ.get("DOC_INTEL_URL", "http://localhost:8003")
ADMIN_DB_URL = os.environ.get("ADMIN_DB_URL", "postgresql://app_admin:admin_pw@localhost:55432/app")


def _healthy(url: str) -> bool:
    try:
        return httpx.get(f"{url}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session")
def compose_up() -> dict[str, str]:
    """Skip the test unless the whole compose stack answers /health."""
    urls = {"actions": ACTIONS_URL, "agent": AGENT_URL, "llm": LLM_URL, "doc_intel": DOC_INTEL_URL}
    down = [name for name, url in urls.items() if not _healthy(url)]
    if down:
        pytest.skip(f"compose stack not running ({', '.join(down)}); run `make up`")
    return urls
