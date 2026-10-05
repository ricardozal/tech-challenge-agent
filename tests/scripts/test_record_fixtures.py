"""make record promotes the answers of a scenario only when the demo reaches its outcome (O-11)."""

import json
from pathlib import Path

import pytest

from scripts.record_fixtures import clear, discard, promote, run_all
from scripts.run_demo import DemoFailure


def write(root: Path, task: str, key: str, origin: str = "recorded") -> Path:
    path = root / task / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"request": {}, "response": {"text": key}, "origin": origin}))
    return path


def snapshot(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): p.read_text() for p in sorted(root.rglob("*.json"))}


@pytest.mark.req("FR-081")
def test_promote_moves_recordings_and_replaces_same_key(tmp_path):
    recording, fixtures = tmp_path / "llm" / "_recording", tmp_path / "llm"
    write(fixtures, "extract", "aaa", origin="seeded")
    write(recording, "extract", "aaa")
    write(recording, "reply", "bbb")

    assert promote(recording, fixtures) == 2
    assert json.loads((fixtures / "extract" / "aaa.json").read_text())["origin"] == "recorded"
    assert (fixtures / "reply" / "bbb.json").exists()
    assert list(recording.rglob("*.json")) == []


@pytest.mark.req("FR-081")
def test_discard_leaves_current_fixtures_untouched(tmp_path):
    recording, fixtures = tmp_path / "llm" / "_recording", tmp_path / "llm"
    write(fixtures, "extract", "aaa", origin="seeded")
    before = {k: v for k, v in snapshot(fixtures).items() if not k.startswith("_recording/")}
    write(recording, "extract", "aaa")

    assert discard(recording) == 1
    assert snapshot(fixtures) == before


def test_clear_empties_the_recording_dir(tmp_path):
    recording = tmp_path / "_recording"
    write(recording, "ocr", "ccc")
    clear(recording)
    assert list(recording.rglob("*.json")) == []


@pytest.mark.req("FR-081")
def test_run_all_promotes_passing_scenarios_and_discards_the_failing_one(tmp_path):
    recording, fixtures = tmp_path / "llm" / "_recording", tmp_path / "llm"
    write(fixtures, "extract", "bad1", origin="seeded")
    scenarios = [tmp_path / "happy_path.yaml", tmp_path / "document_escalation.yaml", tmp_path / "no_spare_key.yaml"]

    def play(path: Path, quiet: bool = True) -> dict:
        name = path.stem
        write(recording, "extract", f"{name}1")
        if name == "document_escalation":
            write(recording, "extract", "bad1")
            raise DemoFailure("paso 14 (upload laura_payslip_bad.png): status esperado 'escalated', obtenido 'active'")
        return {}

    lines: list[str] = []
    code = run_all(scenarios, play, recording, fixtures, out=lines.append)

    assert code == 1
    assert (fixtures / "extract" / "happy_path1.json").exists()
    assert (fixtures / "extract" / "no_spare_key1.json").exists()
    assert not (fixtures / "extract" / "document_escalation1.json").exists()
    assert json.loads((fixtures / "extract" / "bad1.json").read_text())["origin"] == "seeded"
    report = "\n".join(lines)
    assert "document_escalation" in report and "FALLA" in report and "paso 14" in report
    assert "se descartan 2 respuestas; las vigentes no cambian" in report
    assert "2 de 3 guiones grabados" in report


def test_run_all_exits_0_when_every_scenario_passes(tmp_path):
    recording, fixtures = tmp_path / "llm" / "_recording", tmp_path / "llm"

    def play(path: Path, quiet: bool = True) -> dict:
        write(recording, "reply", path.stem)
        return {}

    assert run_all([tmp_path / "happy_path.yaml"], play, recording, fixtures, out=lambda _: None) == 0
    assert (fixtures / "reply" / "happy_path.json").exists()
