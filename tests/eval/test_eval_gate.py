"""make eval: scoring rule of the model comparison, threshold and report (FR-094…FR-098, O-14)."""

import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from scripts.eval_gate import EVAL, request_for, score, summarize
from tests.conftest import LLM_URL

ROOT = Path(__file__).resolve().parents[2]
HEALTH = {"mode": "ollama", "model": "gemma4:12b", "schema_version": 4, "prompt_version": 2}


def case(expected: dict, n: int | None = None, tipo: str = "mensaje", cid: str = "M99") -> dict:
    flat = {k: v for k, v in expected.items() if k != "campos"} | (expected.get("campos") or {})
    return {"id": cid, "tipo": tipo, "esperado": expected, "n_campos": n or len(flat)}


@pytest.mark.req("FR-095")
def test_score_follows_the_comparison_rule():
    c = case({"intencion": "proporcionar_datos",
              "campos": {"segunda_llave": True, "ingreso_monto": 9500, "auto_marca": "Volkswagen", "auto_anio": None}})
    perfect = {"intencion": "proporcionar_datos",
               "campos": {"segunda_llave": True, "ingreso_monto": "9500", "auto_marca": "VOLKSWAGEN.", "auto_anio": None}}
    assert score(c, perfect) == (5, 5)  # n = 1 + 4 expected fields; numbers written as text count
    assert score(c, {**perfect, "campos": {**perfect["campos"], "segunda_llave": "true"}}) == (4, 5)  # bool is exact
    assert score(c, {**perfect, "campos": {**perfect["campos"], "auto_anio": 2019}}) == (4, 5)  # null only for null


@pytest.mark.req("FR-095")
def test_extra_non_null_fields_subtract_and_missing_fields_count_as_null():
    c = case({"intencion": "pregunta", "campos": {}})
    assert score(c, {"intencion": "pregunta", "campos": {"opcion_elegida": None}}) == (1, 1)
    assert score(c, {"intencion": "pregunta", "campos": {"opcion_elegida": 2, "plazo_meses": 24}}) == (0, 1)  # min 0
    with_null = case({"intencion": "proporcionar_datos", "campos": {"codigo_postal": None}})
    assert score(with_null, {"intencion": "proporcionar_datos", "campos": {}}) == (2, 2)  # outside the stage schema


def row(cid: str, ok: int, n: int, tipo: str = "mensaje", valid: bool = True, seconds: float = 5.0) -> dict:
    return {"case": cid, "type": tipo, "ok": ok, "n": n, "valid": valid, "seconds": seconds, "data": {}}


@pytest.mark.req("FR-096")
def test_threshold_is_85_percent_of_fields_and_100_percent_valid_json():
    assert summarize([row("M01", 17, 20)], HEALTH)["passed"] is True  # exactly 85.0%
    assert summarize([row("M01", 849, 1000)], HEALTH)["passed"] is False  # 84.9%
    assert summarize([row("M01", 10, 10), row("D01", 0, 8, "documento", valid=False)], HEALTH)["passed"] is False


@pytest.mark.req("FR-097")
def test_summary_has_model_versions_breakdown_medians_and_failed_cases():
    rows = [row("M01", 2, 2, seconds=4.0), row("M02", 1, 2, seconds=6.0), row("M03", 2, 2, seconds=8.0),
            row("D01", 6, 8, "documento", seconds=15.0)]
    summary = summarize(rows, HEALTH)
    assert (summary["mode"], summary["model"], summary["schema_version"], summary["prompt_version"]) == (
        "ollama", "gemma4:12b", 4, 2)
    assert (summary["cases"], summary["correct_fields"], summary["fields"]) == (4, 11, 14)
    assert summary["by_type"]["mensaje"] == {"correct": 5, "fields": 6, "pct": 83.3}
    assert summary["by_type"]["documento"] == {"correct": 6, "fields": 8, "pct": 75.0}
    assert summary["median_seconds"] == {"mensaje": 6.0, "documento": 15.0}
    assert summary["failed_cases"] == ["M02", "D01"]


@pytest.mark.req("FR-094")
def test_requests_use_the_stage_of_each_case_and_the_recorded_ocr():
    message = {"id": "M17", "tipo": "mensaje", "etapa": "datos_comprobantes", "pregunta_agente": "¿?", "entrada": "x"}
    assert request_for(message)["stage"] == "documents"
    assert request_for({**message, "etapa": "transversal"})["stage"] is None
    doc = request_for({"id": "D01", "tipo": "documento"})
    assert doc["schema_name"] == "documento" and "\x1b[" not in doc["text"] and doc["text"]
    assert doc["text"].startswith("IDENTIFICACIÓN") and "CURP MERL880412MMCNJR09" in doc["text"]
    assert "```" not in doc["text"]  # first copy only, as in the model comparison


def _gate_files() -> set[Path]:
    return set((EVAL / "resultados").glob("gate-*.json"))


@pytest.mark.req("FR-098")
def test_gate_refuses_to_measure_recorded_answers(compose_up):
    if httpx.get(f"{LLM_URL}/health", timeout=5).json().get("mode") != "fake":
        pytest.skip("the gateway is not in LLM_MODE=fake")
    before = _gate_files()
    result = subprocess.run([sys.executable, "scripts/eval_gate.py"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 2
    assert "la medición requiere el modelo real" in result.stderr
    assert _gate_files() == before


@pytest.mark.ollama
@pytest.mark.req("FR-094")
@pytest.mark.req("FR-096")
def test_gate_passes_with_the_real_model(compose_up):
    if httpx.get(f"{LLM_URL}/health", timeout=10).json().get("mode") != "ollama":
        pytest.skip("the gateway is not in LLM_MODE=ollama")
    before = _gate_files()
    result = subprocess.run([sys.executable, "scripts/eval_gate.py"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr
    (new,) = _gate_files() - before
    summary = json.loads(new.read_text(encoding="utf-8"))["summary"]
    assert summary["passed"] is True and summary["cases"] == 37 and summary["schema_version"] == 4
    assert summary["fields_pct"] >= 85 and summary["valid_json_pct"] == 100
