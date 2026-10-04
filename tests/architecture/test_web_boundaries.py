"""The web only talks to agent and actions_api, and writes only through their channels (W-14).

Principles III and IV: the chat writes through the agent channel; the console writes only with
POST /tools/{name} as `advisor`. No other service, database or model is reachable from web/src.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "web" / "src"
SOURCES = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8") for p in sorted(SRC.rglob("*.ts*"))}

FORBIDDEN_TARGETS = (":5432", ":55432", ":8002", ":8003", "11434", "llm_gateway", "doc_intel", "postgres")


def test_there_are_sources():
    assert "web/src/api/actions.ts" in SOURCES and "web/src/api/agent.ts" in SOURCES


@pytest.mark.req("FR-054")
def test_only_config_reads_the_environment_and_only_the_two_api_urls():
    for path, text in SOURCES.items():
        if path == "web/src/config.ts":
            assert set(re.findall(r"import\.meta\.env\.(\w+)", text)) == {"VITE_AGENT_URL", "VITE_ACTIONS_URL"}
        else:
            assert "import.meta.env" not in text, path


@pytest.mark.req("FR-054")
def test_no_other_service_is_reachable():
    for path, text in SOURCES.items():
        for target in FORBIDDEN_TARGETS:
            assert target not in text, f"{path} mentions {target}"


@pytest.mark.req("FR-054")
def test_requests_live_only_in_the_api_clients():
    for path, text in SOURCES.items():
        if not path.startswith("web/src/api/") and path != "web/src/config.ts":
            assert not re.search(r"\bfetch\(\s*`?\$\{(AGENT_URL|ACTIONS_URL)", text), path
            assert "ACTIONS_URL" not in text and "AGENT_URL" not in text, path


@pytest.mark.req("FR-054")
def test_console_writes_only_tools_as_advisor():
    actions = SOURCES["web/src/api/actions.ts"]
    posts = re.findall(r"method:\s*'POST'", actions)
    assert len(posts) == 1
    assert "/tools/${" in actions
    assert "'X-Actor': 'advisor'" in actions


@pytest.mark.req("FR-055")
def test_no_raw_html_rendering():
    for path, text in SOURCES.items():
        assert "dangerouslySetInnerHTML" not in text, path
        assert "innerHTML" not in text, path


def test_api_errors_never_show_english_text_to_the_user():
    """Constitution X: actions_api `detail` and the HTTP status text are English; never user text."""
    for path, text in SOURCES.items():
        assert "statusText" not in text, path
        if path.startswith("web/src/api/"):
            assert not re.search(r"\.detail\b", text), path
