"""Write fixtures/llm/** from the scenario scripts so LLM_MODE=fake answers them (R-11, R-23).

Scenario step formats (fixtures/scenarios/*.yaml):

    - say: "sí, está a mi nombre"
      stage: eligibility                       # stage of the case when the message arrives
      question: "¿El auto está a tu nombre?"   # question the agent asked just before
      extract: {intencion: proporcionar_datos, campos: {auto_a_nombre_propio: true}}

    - upload: fixtures/documents/laura_identification.png
      requested_type: identification
      # ocr_text and extract default to fixtures/documents/specs.yaml (same file name)

The fixture key is contracts.llm.fixture_key, the same function the gateway uses.
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from contracts.llm import fixture_key

try:  # imported as scripts.seed_fixtures (tests) or run as a script (make seed-fixtures)
    from scripts.make_documents import load_specs, ocr_text
except ModuleNotFoundError:
    from make_documents import load_specs, ocr_text

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures" / "llm"


def specs() -> dict:
    return load_specs()


def write(task: str, key: str, request: dict, response: dict) -> Path:
    path = FIXTURES / task / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "request": request,
        "response": response,
        "recorded_at": datetime.now(UTC).isoformat(),
        "model": "seeded-from-scenario",
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def seed(scenario_path: Path) -> int:
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    return seed_steps(scenario.get("steps", []))


def seed_steps(steps: list[dict]) -> int:
    """Write the fixtures of a list of scenario steps (also used by tests)."""
    count = 0
    for step in steps:
        if "say" in step and "extract" in step:
            inputs = {"stage": step.get("stage"), "agent_question": step.get("question"), "text": step["say"]}
            write("extract", fixture_key("extract", "mensaje", inputs), {"schema_name": "mensaje", **inputs}, step["extract"])
            count += 1
        if "upload" in step:
            spec = specs().get(Path(step["upload"]).stem, {})
            step = {"ocr_text": ocr_text(spec) if spec else None, "extract": spec.get("extract"), **step}
            content = (ROOT / step["upload"]).read_bytes()
            ocr_inputs = {"sha256": hashlib.sha256(content).hexdigest()}
            write("ocr", fixture_key("ocr", None, ocr_inputs), ocr_inputs, {"text": step["ocr_text"]})
            inputs = {"stage": None, "agent_question": None, "text": step["ocr_text"]}
            write("extract", fixture_key("extract", "documento", inputs), {"schema_name": "documento", **inputs},
                  step["extract"])
            count += 2
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenarios", nargs="*", type=Path)
    args = parser.parse_args()
    paths = args.scenarios or sorted((ROOT / "fixtures" / "scenarios").glob("*.yaml"))
    total = 0
    for path in paths:
        n = seed(path)
        total += n
        print(f"{path.name}: {n} fixtures")
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
