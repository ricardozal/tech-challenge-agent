"""Which recorded answers the 4 demos use in LLM_MODE=fake: authentic, seeded or missing (O-12, FR-083).

    make up && make fixtures-status [PRUNE=1]

Plays every scenario against the gateway's usage counter (GET/DELETE /v1/fixtures/usage), read after
each step so every seeded or missing answer is reported with its scenario and step, and lists the
fixtures under fixtures/llm/<task>/ that no demo used (--prune deletes them; tests that seed their own
answers write them again when they run). Exit 0: no seeded or missing answer · 1: some · 2: no gateway
in fake mode.
"""

import argparse
import os
import sys
from pathlib import Path

import httpx

try:  # imported as scripts.fixtures_status (tests) or run as a script (make fixtures-status)
    from scripts.run_demo import DemoFailure, play
except ModuleNotFoundError:
    from run_demo import DemoFailure, play

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures" / "llm"
SCENARIOS = ROOT / "fixtures" / "scenarios"
LLM_URL = os.environ.get("LLM_URL", "http://localhost:8002")
TASKS = ("extract", "ocr", "reply")
ORIGIN_ES = {"seeded": ("respuesta sembrada", "respuestas sembradas"),
             "missing": ("respuesta faltante", "respuestas faltantes")}


def step_problems(scenario: str, step: str, usage: dict) -> list[str]:
    """One line per task with seeded or missing answers in this step's usage snapshot."""
    lines = []
    for task, by_origin in usage["by_task"].items():
        for origin, (one, many) in ORIGIN_ES.items():
            keys = by_origin.get(origin) or []
            if keys:
                lines.append(f"{scenario} · {step}: {len(keys)} {one if len(keys) == 1 else many} en {task}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prune", action="store_true", help="delete the fixtures no demo used")
    args = parser.parse_args()
    with httpx.Client(base_url=LLM_URL, timeout=10) as http:
        try:
            mode = http.get("/health").json().get("mode")
        except (httpx.HTTPError, ValueError):
            mode = None
        if mode != "fake":
            print("El gateway no está en LLM_MODE=fake; levántalo con make up.", file=sys.stderr)
            return 2

        used: set[tuple[str, str]] = set()
        problems: list[str] = []
        totals = {"recorded": 0, "seeded": 0, "missing": 0}
        print(f"{'guion':<22} {'auténticas':>10} {'sembradas':>10} {'faltantes':>10}")
        for path in sorted(SCENARIOS.glob("*.yaml")):
            http.delete("/v1/fixtures/usage").raise_for_status()
            counts = {"recorded": 0, "seeded": 0, "missing": 0}

            def after_step(step: str, scenario: str = path.stem, counts: dict = counts) -> None:
                usage = http.get("/v1/fixtures/usage").json()
                for origin in counts:
                    counts[origin] += usage["counts"].get(origin, 0)
                for task, by_origin in usage["by_task"].items():
                    for keys in by_origin.values():
                        used.update((task, key) for key in keys)
                problems.extend(step_problems(scenario, step, usage))
                http.delete("/v1/fixtures/usage").raise_for_status()

            try:
                play(path, quiet=True, after_step=after_step)
            except (DemoFailure, httpx.HTTPError) as exc:
                problems.append(f"{path.stem}: el demo no llegó a su resultado ({exc})")
            for origin in totals:
                totals[origin] += counts[origin]
            print(f"{path.stem:<22} {counts['recorded']:>10} {counts['seeded']:>10} {counts['missing']:>10}")
        print(f"{'total':<22} {totals['recorded']:>10} {totals['seeded']:>10} {totals['missing']:>10}")

    unused = [p for task in TASKS for p in sorted((FIXTURES / task).glob("*.json")) if (task, p.stem) not in used]
    if args.prune:
        for path in unused:
            path.unlink()
        print(f"fixtures sin uso en los demos: {len(unused)} (borrados)")
    else:
        print(f"fixtures sin uso en los demos: {len(unused)} (make fixtures-status PRUNE=1 para borrarlos)")
    for problem in problems:
        print(f"  · {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
