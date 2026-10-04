"""Generate TRACEABILITY.md from @pytest.mark.req("FR-xxx") markers and Playwright @FR-xxx tags (R-21, W-13).

Exits with code 1 and lists the FRs of the specs that have no test.
"""

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = [ROOT / "specs" / "001-credit-agent-core" / "spec.md", ROOT / "specs" / "002-demo-web" / "spec.md"]
TEST_DIRS = [ROOT / "tests", *sorted((ROOT / "services").glob("*/tests"))]
PLAYWRIGHT_DIR = ROOT / "web" / "e2e"
FR_ID = re.compile(r"\*\*(FR-\d{3})\*\*")
# test('title' | "title" | `title`, { tag: [...] }, ...)
PW_TEST = re.compile(r"\btest\(\s*(['\"`])(?P<title>.+?)\1\s*,\s*\{\s*tag:\s*\[(?P<tags>[^\]]*)\]", re.S)
PW_TAG = re.compile(r"@(FR-\d{3})")


def _req_ids(decorators: list[ast.expr]) -> list[str]:
    ids = []
    for node in decorators:
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "req"
                and call.args
                and isinstance(call.args[0], ast.Constant)
            ):
                ids.append(str(call.args[0].value))
    return ids


def collect() -> dict[str, list[str]]:
    found: dict[str, list[str]] = defaultdict(list)
    for test_dir in TEST_DIRS:
        for path in sorted(test_dir.rglob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            rel = path.relative_to(ROOT)
            module_ids: list[str] = []
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
                ):
                    module_ids = _req_ids([node.value])
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                    for fr in [*module_ids, *_req_ids(node.decorator_list)]:
                        found[fr].append(f"{rel}::{node.name}")
    for path in sorted(PLAYWRIGHT_DIR.glob("*.spec.ts")):
        rel = path.relative_to(ROOT)
        for match in PW_TEST.finditer(path.read_text(encoding="utf-8")):
            for fr in PW_TAG.findall(match["tags"]):
                found[fr].append(f"{rel}::{match['title']}")
    return found


def main() -> int:
    spec_ids = sorted({fr for spec in SPECS for fr in FR_ID.findall(spec.read_text(encoding="utf-8"))})
    found = collect()
    missing = [fr for fr in spec_ids if not found.get(fr)]
    lines = [
        "# Traceability",
        "",
        "Generado por `scripts/traceability.py` a partir de `@pytest.mark.req` y de los tags `@FR-xxx` de "
        "Playwright (`web/e2e/`); no editar a mano.",
        "",
        f"Requisitos: {len(spec_ids)} · con test: {len(spec_ids) - len(missing)} · sin test: {len(missing)}",
        "",
        "| Requisito | Tests |",
        "|---|---|",
    ]
    for fr in spec_ids:
        tests = found.get(fr, [])
        lines.append(f"| {fr} | {'<br>'.join(f'`{t}`' for t in tests) if tests else '**sin test**'} |")
    (ROOT / "TRACEABILITY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if missing:
        print("FR sin test: " + ", ".join(missing))
        return 1
    print(f"TRACEABILITY.md: {len(spec_ids)} FR con test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
