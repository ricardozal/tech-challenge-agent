"""docker-compose.yml respects the boundaries (R-20, Principles III and V)."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SERVICES = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]


def env(service: str) -> dict:
    return SERVICES[service].get("environment", {})


def volumes(service: str) -> list[str]:
    return SERVICES[service].get("volumes", [])


def test_topology_is_the_feature_001_subset():
    assert set(SERVICES) == {"postgres", "actions_api", "agent", "llm_gateway", "doc_intel"}


@pytest.mark.req("FR-051")
def test_only_the_gateway_knows_the_llm_mode_and_ollama():
    for service in SERVICES:
        has = {"LLM_MODE", "OLLAMA_URL"} & set(env(service))
        assert has == ({"LLM_MODE", "OLLAMA_URL"} if service == "llm_gateway" else set()), service
    assert env("llm_gateway")["LLM_MODE"] == "${LLM_MODE:-fake}"


def test_doc_intel_has_no_database_and_no_volumes():
    assert not any("DATABASE" in key for key in env("doc_intel"))
    assert volumes("doc_intel") == []


def test_documents_volume_only_on_actions_api():
    owners = [s for s in SERVICES if any(v.startswith("documents:") for v in volumes(s))]
    assert owners == ["actions_api"]


def test_agent_connects_with_its_own_role_and_schema():
    assert env("agent")["DATABASE_URL"].startswith("postgresql://agent_rw:")
    assert "search_path%3Dagent" in env("agent")["DATABASE_URL"]
    assert env("actions_api")["DATABASE_URL"].startswith("postgresql://actions_rw:")
