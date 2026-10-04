"""Write web/public/scenarios.json from the 001 scenario scripts (specs/002-demo-web W-05, W-06).

    uv run python scripts/export_web_scenarios.py      # make web-scenarios

The chat suggests exactly the `say` texts of the scripts, paired with the agent question they
answer, so LLM_MODE=fake understands them (R-11). Document slots carry the agent's question for
each document type, so the chat can highlight the one the agent is asking for.
tests/web/test_scenarios_export.py fails if the committed file is out of date.
"""

import json
from pathlib import Path
from typing import Any

import yaml

from agent.questions import DOCUMENT_QUESTIONS
from contracts.common import DocumentType

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "fixtures" / "scenarios"
OUTPUT = ROOT / "web" / "public" / "scenarios.json"

# The four scenarios of the web. document_failed joins both branches of demo 3: the messages are the
# same and the income proof slot offers the payslip that does not match and the right one.
MANIFEST: list[dict[str, Any]] = [
    {
        "id": "happy_path",
        "title": "Happy path",
        "description": "Auto elegible con segunda llave y documentos en orden: termina en OK para financiera.",
        "expected_results": ["ok_for_lender"],
        "source_scripts": ["happy_path"],
    },
    {
        "id": "eligibility_rejection",
        "title": "Rechazo por auto",
        "description": "El auto está a nombre de otra persona: el sistema rechaza sin consultar Buró.",
        "expected_results": ["rejected"],
        "source_scripts": ["eligibility_rejection"],
    },
    {
        "id": "document_failed",
        "title": "Documento fallido",
        "description": (
            "El recibo de nómina no cuadra con el ingreso declarado. Envía el correcto para llegar a OK, "
            "o reenvía el que no cuadra hasta que el caso se escale a un asesor."
        ),
        "expected_results": ["ok_for_lender", "escalated"],
        "source_scripts": ["document_correction", "document_escalation"],
    },
    {
        "id": "no_spare_key",
        "title": "Sin segunda llave",
        "description": "Auto sin segunda llave: se cotiza su fabricación, entra al plan de pagos y el caso llega a OK.",
        "expected_results": ["ok_for_lender"],
        "source_scripts": ["no_spare_key"],
    },
]

DOCUMENT_LABELS: dict[str, tuple[str, str]] = {
    "laura_identification.png": ("Identificación oficial", "ok"),
    "laura_payslip.png": ("Recibo de nómina", "ok"),
    "laura_payslip_low.png": ("Recibo de nómina — no cuadra", "mismatch"),
    "laura_proof_of_address.png": ("Comprobante de domicilio", "ok"),
    "laura_invoice.png": ("Factura del auto", "ok"),
    "maria_identification.png": ("Identificación oficial", "ok"),
    "maria_bank_statement.png": ("Estado de cuenta", "ok"),
    "maria_proof_of_address.png": ("Comprobante de domicilio", "ok"),
    "maria_invoice.png": ("Factura del auto", "ok"),
}

INCOME_PROOF_TYPES = {DocumentType.payslip, DocumentType.bank_statement}


def _steps(script: str) -> list[dict[str, Any]]:
    return yaml.safe_load((SCRIPTS / f"{script}.yaml").read_text(encoding="utf-8"))["steps"]


def _messages(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"stage": s.get("stage"), "question": s.get("question"), "text": s["say"]} for s in steps if "say" in s]


def _client_name(steps: list[dict[str, Any]]) -> str:
    for step in steps:
        name = (step.get("extract") or {}).get("campos", {}).get("nombre_completo")
        if name:
            return name
    raise ValueError("the script never states the client's full name")


def _slot(requested_type: DocumentType) -> str:
    return "income_proof" if requested_type in INCOME_PROOF_TYPES else requested_type.value


def _documents(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slots: dict[str, dict[str, Any]] = {}
    for step in steps:
        if "upload" not in step:
            continue
        requested = DocumentType(step["requested_type"])
        slot = _slot(requested)
        question_key = slot if slot == "income_proof" else requested
        entry = slots.setdefault(slot, {"slot": slot, "question": DOCUMENT_QUESTIONS[question_key].text, "options": []})
        name = Path(step["upload"]).name
        if any(option["file"] == f"documents/{name}" for option in entry["options"]):
            continue
        label, variant = DOCUMENT_LABELS[name]
        entry["options"].append(
            {"file": f"documents/{name}", "requested_type": requested.value, "label": label, "variant": variant}
        )
    return list(slots.values())


def build() -> dict[str, Any]:
    scenarios = []
    generated_from = []
    for item in MANIFEST:
        scripts = [_steps(name) for name in item["source_scripts"]]
        generated_from += [f"fixtures/scenarios/{name}.yaml" for name in item["source_scripts"]]
        messages = _messages(scripts[0])
        for other in scripts[1:]:
            if _messages(other) != messages:
                raise ValueError(f"{item['id']}: the `say` steps of {item['source_scripts']} differ")
        scenarios.append(
            {
                "id": item["id"],
                "title": item["title"],
                "description": item["description"],
                "client_name": _client_name(scripts[0]),
                "expected_results": item["expected_results"],
                "source_scripts": item["source_scripts"],
                "messages": messages,
                "documents": _documents([step for steps in scripts for step in steps]),
            }
        )
    return {"generated_from": generated_from, "scenarios": scenarios}


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)}: {len(MANIFEST)} escenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
