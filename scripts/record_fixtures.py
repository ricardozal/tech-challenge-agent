"""Record the 4 demos with the real models and keep only what reached its outcome (O-11, FR-081).

    LLM_MODE=record make up && make record [ONLY="happy_path no_spare_key"]

The gateway (LLM_MODE=record) writes every model answer to fixtures/llm/_recording/. For each scenario
this script empties that directory, plays the scenario and, if the demo reaches its expected outcome,
moves what was recorded into fixtures/llm/ (replacing by key); otherwise it discards it, so the current
answers of that demo do not change. Exit 0: every scenario promoted · 1: some failed · 2: no gateway in
record mode.
"""

import argparse
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import httpx

try:  # imported as scripts.record_fixtures (tests) or run as a script (make record)
    from scripts.run_demo import DemoFailure, play
except ModuleNotFoundError:
    from run_demo import DemoFailure, play

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures" / "llm"
RECORDING = FIXTURES / "_recording"
SCENARIOS = ROOT / "fixtures" / "scenarios"
LLM_URL = os.environ.get("LLM_URL", "http://localhost:8002")


def _files(root: Path) -> list[Path]:
    return sorted(root.glob("*/*.json")) if root.exists() else []


def clear(recording: Path) -> None:
    for path in _files(recording):
        path.unlink()


def promote(recording: Path, fixtures: Path) -> int:
    """Move every recorded answer into fixtures/<task>/, replacing a fixture with the same key."""
    files = _files(recording)
    for path in files:
        target = fixtures / path.parent.name / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), target)
    return len(files)


def discard(recording: Path) -> int:
    files = _files(recording)
    clear(recording)
    return len(files)


def run_all(
    scenarios: list[Path],
    play: Callable[..., dict],
    recording: Path,
    fixtures: Path,
    out: Callable[[str], None] = print,
) -> int:
    ok = 0
    for path in scenarios:
        clear(recording)
        try:
            play(path, quiet=True)
        except (DemoFailure, httpx.HTTPError) as exc:
            n = discard(recording)
            out(f"{path.stem:<22} FALLA   {exc}")
            out(f"{'':<22}         se descartan {n} respuestas; las vigentes no cambian")
            continue
        n = promote(recording, fixtures)
        ok += 1
        out(f"{path.stem:<22} OK      {n:>3} respuestas grabadas → fixtures/llm")
    out(f"{ok} de {len(scenarios)} guiones grabados")
    return 0 if ok == len(scenarios) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenarios", nargs="*", help="scenario names (default: all in fixtures/scenarios)")
    args = parser.parse_args()
    try:
        mode = httpx.get(f"{LLM_URL}/health", timeout=10).json().get("mode")
    except (httpx.HTTPError, ValueError):
        mode = None
    if mode != "record":
        print("El gateway no está en LLM_MODE=record; levántalo con LLM_MODE=record make up.", file=sys.stderr)
        return 2
    paths = sorted(SCENARIOS.glob("*.yaml"))
    if args.scenarios:
        paths = [SCENARIOS / f"{name}.yaml" for name in args.scenarios]
    return run_all(paths, play, RECORDING, FIXTURES)


if __name__ == "__main__":
    sys.exit(main())
