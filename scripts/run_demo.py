"""Play a demo scenario against the agent and check its expected outcome (R-23).

    uv run python scripts/run_demo.py fixtures/scenarios/happy_path.yaml [--repeat N] [--quiet]

Steps: `say` (message), `upload` (document), `advisor` (advisor tool on actions_api).
`expected`: final `status`/`stage`, `tools_called`, `tools_not_called`, `events`.
"""

import argparse
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENT_URL = os.environ.get("AGENT_URL", "http://localhost:8001")
ACTIONS_URL = os.environ.get("ACTIONS_URL", "http://localhost:8000")


class DemoFailure(AssertionError):
    pass


def _advisor(http: httpx.Client, case_id: str, step: dict[str, Any], n: int) -> dict[str, Any]:
    case = http.get(f"{ACTIONS_URL}/cases/{case_id}").json()
    call = {
        "context": {"case_id": case_id, "idempotency_key": f"advisor-{n}-{uuid.uuid4()}", "expected_version": case["version"]},
        "input": step.get("input", {}),
    }
    return http.post(f"{ACTIONS_URL}/tools/{step['advisor']}", json=call, headers={"X-Actor": "advisor"}).json()


def play(path: Path, quiet: bool = False) -> dict[str, Any]:
    scenario = yaml.safe_load(path.read_text(encoding="utf-8"))
    say = (lambda *a: None) if quiet else print
    run_id = uuid.uuid4().hex[:8]
    started = time.monotonic()
    with httpx.Client(timeout=330) as http:
        created = http.post(f"{AGENT_URL}/cases", headers={"Idempotency-Key": f"{scenario['name']}-{run_id}"})
        created.raise_for_status()
        body = created.json()
        case_id = body["case_id"]
        say(f"\n=== {scenario['name']} · caso {case_id}")
        say(f"agente> {body['reply']}")
        last_question = None
        for n, step in enumerate(scenario.get("steps", []), start=1):
            key = f"{scenario['name']}-{run_id}-{n}"
            if "say" in step:
                if step.get("question") and last_question and step["question"] != last_question:
                    raise DemoFailure(f"paso {n}: el agente preguntó {last_question!r}, el guion espera {step['question']!r}")
                say(f"cliente> {step['say']}")
                resp = http.post(f"{AGENT_URL}/cases/{case_id}/messages", json={"text": step["say"]},
                                 headers={"Idempotency-Key": key})
            elif "upload" in step:
                say(f"cliente> [envía {step['requested_type']}: {step['upload']}]")
                file_path = ROOT / step["upload"]
                resp = http.post(
                    f"{AGENT_URL}/cases/{case_id}/documents",
                    files={"file": (file_path.name, file_path.read_bytes(), "image/png")},
                    data={"requested_type": step["requested_type"]},
                    headers={"Idempotency-Key": key},
                )
            elif "advisor" in step:
                result = _advisor(http, case_id, step, n)
                say(f"asesor> {step['advisor']} → {result.get('outcome')} {result.get('rejection') or ''}")
                continue
            else:
                raise DemoFailure(f"paso {n}: tipo de paso desconocido {step}")
            if resp.status_code != 200:
                raise DemoFailure(f"paso {n}: HTTP {resp.status_code} {resp.text[:300]}")
            turn = resp.json()
            calls = ", ".join(f"{c['tool']}:{c['outcome']}" for c in turn["tool_calls"] if c["tool"] != "append_message")
            say(f"agente> {turn['reply']}" + (f"   [{calls}]" if calls else ""))
            conversation = http.get(f"{AGENT_URL}/cases/{case_id}/conversation").json()
            last_question = conversation["state"].get("last_question")

        case = http.get(f"{ACTIONS_URL}/cases/{case_id}").json()
        audit = http.get(f"{ACTIONS_URL}/cases/{case_id}/audit").json()
    elapsed = time.monotonic() - started

    say(f"\n--- estado final: stage={case['stage']} status={case['status']} version={case['version']}")
    say("--- registro de acciones:")
    for entry in audit:
        if entry["tool"] == "append_message":
            continue
        events = ", ".join(e["type"] for e in entry["events"])
        say(f"  #{entry['id']:<4} {entry['actor']:<7} {entry['tool']:<26} {entry['outcome']:<8} "
            f"{entry['rejection_code'] or ''} {events}")
    check(scenario.get("expected", {}), case, audit)
    say(f"--- OK en {elapsed:.1f}s")
    return {"case": case, "audit": audit, "elapsed_s": elapsed,
            "tools": [e["tool"] for e in audit if e["tool"] != "append_message"]}


def check(expected: dict[str, Any], case: dict[str, Any], audit: list[dict[str, Any]]) -> None:
    accepted = {e["tool"] for e in audit if e["outcome"] == "accepted"}
    called = {e["tool"] for e in audit}
    events = {ev["type"] for e in audit for ev in e["events"]}
    problems = []
    for field in ("status", "stage"):
        if field in expected and case[field] != expected[field]:
            problems.append(f"{field}: esperado {expected[field]!r}, obtenido {case[field]!r}")
    problems += [f"no se llamó {t}" for t in expected.get("tools_called", []) if t not in accepted]
    problems += [f"se llamó {t}" for t in expected.get("tools_not_called", []) if t in called]
    problems += [f"falta el evento {ev}" for ev in expected.get("events", []) if ev not in events]
    if problems:
        raise DemoFailure("; ".join(problems))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenarios", nargs="+", type=Path)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    failures = 0
    for i in range(args.repeat):
        for path in args.scenarios:
            try:
                play(path, quiet=args.quiet or i > 0)
            except (DemoFailure, httpx.HTTPError) as exc:
                failures += 1
                print(f"FALLÓ {path.name} (corrida {i + 1}): {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
