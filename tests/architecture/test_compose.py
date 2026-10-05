"""docker-compose.yml respects the boundaries (R-20, Principles III and V)."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SERVICES = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]


def env(service: str) -> dict:
    return SERVICES[service].get("environment", {})


def volumes(service: str) -> list[str]:
    return SERVICES[service].get("volumes", [])


def test_topology_is_the_reference_topology():
    assert set(SERVICES) == {"postgres", "actions_api", "agent", "llm_gateway", "doc_intel", "web", "phoenix"}


@pytest.mark.req("FR-091")
def test_phoenix_is_a_pinned_local_console_with_its_own_volume():
    phoenix = SERVICES["phoenix"]
    assert phoenix["image"] == "arizephoenix/phoenix:version-20.19.0"
    assert "6006:6006" in phoenix["ports"]
    assert any(v.startswith("phoenix_data:") for v in volumes("phoenix"))


@pytest.mark.req("FR-091")
def test_only_agent_gateway_and_doc_intel_export_traces():
    exporters = {s for s in SERVICES if "PHOENIX_COLLECTOR_ENDPOINT" in env(s)}
    assert exporters == {"agent", "llm_gateway", "doc_intel"}
    assert {env(s)["PHOENIX_COLLECTOR_ENDPOINT"] for s in exporters} == {"http://phoenix:6006"}


@pytest.mark.req("FR-092")
def test_no_service_needs_phoenix_to_start():
    assert not [s for s, spec in SERVICES.items() if "phoenix" in (spec.get("depends_on") or {})]


@pytest.mark.req("FR-054")
def test_web_has_no_database_llm_or_volumes():
    assert not any("DATABASE" in key for key in env("web"))
    assert not {"LLM_MODE", "OLLAMA_URL"} & set(env("web"))
    assert volumes("web") == []
    assert set(SERVICES["web"]["depends_on"]) == {"agent", "actions_api"}


def test_web_origins_on_agent_and_actions_api():
    for service in ("agent", "actions_api"):
        assert env(service)["WEB_ORIGINS"] == "${WEB_ORIGINS:-http://localhost:8080}", service


@pytest.mark.req("FR-051")
@pytest.mark.req("FR-076")
def test_only_the_gateway_knows_the_llm_mode_and_ollama():
    for service in SERVICES:
        has = {"LLM_MODE", "OLLAMA_URL"} & set(env(service))
        assert has == ({"LLM_MODE", "OLLAMA_URL"} if service == "llm_gateway" else set()), service
    assert env("llm_gateway")["LLM_MODE"] == "${LLM_MODE:-fake}"


@pytest.mark.req("FR-076")
def test_only_the_gateway_config_reads_the_llm_mode_variable():
    """Switching modes is one environment variable: no other code reads it (SC-017)."""
    reads = re.compile(r"""(environ(\.get)?\(|environ\[|getenv\()\s*["']LLM_MODE["']""")
    sources = [*ROOT.glob("services/*/src/**/*.py"), *ROOT.glob("scripts/*.py"), *ROOT.glob("web/src/**/*.ts*")]
    readers = sorted(str(p.relative_to(ROOT)) for p in sources if reads.search(p.read_text(encoding="utf-8")))
    assert readers == ["services/llm_gateway/src/llm_gateway/config.py"]


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
