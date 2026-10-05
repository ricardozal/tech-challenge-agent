"""LLM quality gate (Principle VIII, R-13, O-14): extraction over eval/casos_eval.jsonl must reach at
least 85% correct fields and 100% valid JSON, measured through the real llm_gateway.

    LLM_MODE=ollama make up && make eval

Each message case is sent with its stage, so the gateway uses the message schema of that stage
(eval/esquemas.json v4, O-13); `transversal` cases go without stage (full schema).
Exit codes: 0 passes · 1 does not pass (failed cases listed) · 2 the gateway is in LLM_MODE=fake or does
not answer (nothing is measured and no result file is written).

Scoring follows the `puntaje` rule of eval/esquemas.json exactly as the model comparison applied it:
n = 1 (intent or document type) + expected fields; numbers and booleans exact (numbers written as
text count), text uppercase without accents with punctuation as spaces; null only matches an expected
null; every extra non-null field subtracts 1 (minimum 0).
Documents use the recorded OCR text of eval/ocr_D0x.txt (first copy, without ANSI sequences).
"""

import argparse
import json
import os
import re
import statistics
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval"
LLM_URL = os.environ.get("LLM_URL", "http://localhost:8002")
MIN_FIELDS, MIN_VALID = 0.85, 1.0
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
STAGES = {"elegibilidad": "eligibility", "perfilamiento": "profiling", "simulacion": "simulation",
          "datos_comprobantes": "documents", "documentos": "documents"}


def clean_ocr(path: Path) -> str:
    first = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            break
        first.append(line)
    return ANSI.sub("", "\n".join(first)).strip()


def norm_text(value: str) -> str:
    """Uppercase, no accents, punctuation as spaces, single spaces (same rule as the model comparison)."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", plain.upper())).strip()


def same(expected, got) -> bool:
    """Numbers and booleans exact (numbers written as text count), text normalized, null only for null."""
    if expected is None:
        return got is None
    if isinstance(expected, bool):
        return isinstance(got, bool) and got == expected
    if isinstance(expected, int | float):
        if isinstance(got, bool):
            return False
        try:
            return abs(float(got) - float(expected)) < 1e-6
        except (TypeError, ValueError):
            return False
    if isinstance(expected, str):
        if isinstance(got, bool) or not isinstance(got, str | int | float):
            return False
        return norm_text(str(got)) == norm_text(expected)
    return got == expected


def flatten(data: dict) -> dict:
    """First-level keys (except `campos`) plus the content of `campos`."""
    flat = {k: v for k, v in data.items() if k != "campos"}
    if isinstance(data.get("campos"), dict):
        flat.update(data["campos"])
    return flat


def score(case: dict, data: dict) -> tuple[int, int]:
    expected, got = flatten(case["esperado"]), flatten(data)
    correct = sum(same(value, got.get(key)) for key, value in expected.items())
    extra = [key for key, value in got.items() if key not in expected and value is not None]
    return max(0, correct - len(extra)), len(expected)


def request_for(case: dict) -> dict:
    if case["tipo"] == "mensaje":
        return {"schema_name": "mensaje", "stage": STAGES.get(case["etapa"]), "agent_question": case["pregunta_agente"],
                "text": case["entrada"]}
    return {"schema_name": "documento", "text": clean_ocr(EVAL / f"ocr_{case['id']}.txt")}


def summarize(rows: list[dict], health: dict) -> dict:
    """Totals over the whole set (the threshold), plus per-type breakdown, medians and failed cases."""
    total_ok = sum(r["ok"] for r in rows)
    total_n = sum(r["n"] for r in rows)
    fields = total_ok / total_n if total_n else 0.0
    valid = sum(r["valid"] for r in rows) / len(rows) if rows else 0.0
    by_type, medians = {}, {}
    for tipo in ("mensaje", "documento"):
        typed = [r for r in rows if r["type"] == tipo]
        if not typed:
            continue
        ok, n = sum(r["ok"] for r in typed), sum(r["n"] for r in typed)
        by_type[tipo] = {"correct": ok, "fields": n, "pct": round(100 * ok / n, 1) if n else 0.0}
        medians[tipo] = round(statistics.median(r["seconds"] for r in typed), 1)
    return {
        "at": datetime.now().isoformat(timespec="seconds"),
        "mode": health.get("mode"),
        "model": health.get("model"),
        "schema_version": health.get("schema_version"),
        "prompt_version": health.get("prompt_version"),
        "cases": len(rows),
        "correct_fields": total_ok,
        "fields": total_n,
        "fields_pct": round(fields * 100, 1),
        "valid_json_pct": round(valid * 100, 1),
        "by_type": by_type,
        "median_seconds": medians,
        "failed_cases": [r["case"] for r in rows if not r["valid"] or r["ok"] < r["n"]],
        "passed": round(fields, 4) >= MIN_FIELDS and valid >= MIN_VALID,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", nargs="+", help="case ids (default: all)")
    args = parser.parse_args()

    cases = [json.loads(line) for line in (EVAL / "casos_eval.jsonl").read_text(encoding="utf-8").splitlines() if line]
    if args.cases:
        cases = [c for c in cases if c["id"] in set(args.cases)]
    with httpx.Client(base_url=LLM_URL, timeout=600) as http:
        try:
            health = http.get("/health").json()
        except (httpx.HTTPError, ValueError):
            health = {}
        if health.get("mode") not in ("ollama", "record"):
            print("El gateway está en LLM_MODE=fake o no responde; la medición requiere el modelo real "
                  "(LLM_MODE=ollama make up).", file=sys.stderr)
            return 2
        rows = []
        for case in cases:
            started = time.monotonic()
            resp = http.post("/v1/extract", json=request_for(case))
            elapsed = round(time.monotonic() - started, 1)
            if resp.status_code != 200:
                ok, n, valid = 0, case["n_campos"], False
                data = {"error": resp.json().get("error")}
            else:
                data = resp.json()["data"]
                (ok, n), valid = score(case, data), True
            rows.append({"case": case["id"], "type": case["tipo"], "ok": ok, "n": n, "valid": valid,
                         "seconds": elapsed, "data": data})
            print(f"{case['id']:<4} {ok:>2}/{n:<2} {elapsed:>6}s  {case.get('que_prueba', '')[:70]}", flush=True)

    summary = summarize(rows, health)
    out = EVAL / "resultados" / f"gate-{datetime.now():%Y-%m-%d_%H%M%S}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    by_type = summary["by_type"]
    print()
    print("   ".join(f"{t}s: {v['correct']}/{v['fields']} = {v['pct']}%" for t, v in by_type.items()))
    print(f"campos correctos: {summary['correct_fields']}/{summary['fields']} = {summary['fields_pct']}% "
          f"(mínimo {MIN_FIELDS:.0%}) · JSON válido: {summary['valid_json_pct']}% (mínimo 100%)")
    medians = " · ".join(f"mediana {t} {v}s" for t, v in summary["median_seconds"].items())
    print(f"modelo {summary['model']} · esquema v{summary['schema_version']} · modo {summary['mode']} · {medians}")
    if not summary["passed"]:
        print(f"casos con fallas: {', '.join(summary['failed_cases'])}")
    print(f"{'PASA' if summary['passed'] else 'NO PASA'} · resultados en {out.relative_to(ROOT)}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
