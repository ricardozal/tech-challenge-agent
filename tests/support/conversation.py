"""Play a short conversation against the compose agent with fixtures seeded for its messages."""

import uuid
from pathlib import Path

from scripts.seed_fixtures import seed_steps

Q_NAME = "¿Me compartes tu nombre completo?"
Q_VEHICLE = "¿Qué auto es? Dime marca, modelo y año."
Q_OWN = "¿El auto está a tu nombre?"
Q_DEBT = "¿El auto tiene algún adeudo, crédito o gravamen?"
Q_KEY = "¿Tienes la segunda llave del auto?"
Q_ADDRESS = "¿Cuál es tu domicilio, con código postal?"
Q_INCOME = "¿Cuál es tu situación laboral y cuánto ganas?"
Q_CONSENT = "¿Nos autorizas consultar tu historial en Buró de Crédito?"
Q_OPTION = "¿Cuál opción prefieres?"
Q_ID = "Envíame una foto de tu identificación oficial (INE o pasaporte)."
Q_INCOME_PROOF = "Envíame tu comprobante de ingresos más reciente (recibo de nómina o estado de cuenta)."
Q_PROOF_OF_ADDRESS = "¿Me envías tu comprobante de domicilio?"
Q_INVOICE = "Envíame la factura del auto."
ROOT = Path(__file__).resolve().parents[2]


def say(text: str, question: str, stage: str = "eligibility", intent: str = "proporcionar_datos", **campos) -> dict:
    return {"say": text, "stage": stage, "question": question, "extract": {"intencion": intent, "campos": campos}}


def converse(stack: dict, steps: list[dict]) -> tuple[str, list[dict]]:
    seed_steps(steps)
    http = stack["http"]
    case_id = http.post(f"{stack['agent']}/cases").json()["case_id"]
    turns = []
    for step in steps:
        if "upload" in step:
            path = ROOT / step["upload"]
            resp = http.post(
                f"{stack['agent']}/cases/{case_id}/documents",
                files={"file": (path.name, path.read_bytes(), "image/png")},
                data={"requested_type": step["requested_type"]},
                headers={"Idempotency-Key": f"t-{uuid.uuid4()}"},
            )
        else:
            resp = http.post(
                f"{stack['agent']}/cases/{case_id}/messages",
                json={"text": step["say"]},
                headers={"Idempotency-Key": f"t-{uuid.uuid4()}"},
            )
        assert resp.status_code == 200, resp.text
        turns.append(resp.json())
    return case_id, turns


def tools(turn: dict) -> list[str]:
    return [c["tool"] for c in turn["tool_calls"] if c["tool"] != "append_message"]


def eligible_steps(name: str, make: str, model: str, year: int, spare_key: bool = True) -> list[dict]:
    """Messages that take a new case through eligibility into profiling."""
    return [
        say(f"me llamo {name}", Q_NAME, nombre_completo=name),
        say(f"un {make} {model} {year}", Q_VEHICLE, auto_marca=make, auto_modelo=model, auto_anio=year),
        say("sí, está a mi nombre", Q_OWN, auto_a_nombre_propio=True),
        say("no debo nada", Q_DEBT, adeudos_vehiculo=False),
        say("sí tengo las dos llaves" if spare_key else "no tengo la segunda llave", Q_KEY, segunda_llave=spare_key),
    ]


def upload(name: str, requested_type: str) -> dict:
    return {"upload": f"fixtures/documents/{name}.png", "requested_type": requested_type}


def laura_to_documents() -> list[dict]:
    """Laura Méndez Rojas: eligible Jetta 2019, employed, 20,000 monthly, picks option 1."""
    return [
        *eligible_steps("Laura Méndez Rojas", "Volkswagen", "Jetta", 2019),
        say("Av. Morelos 245, Col. Centro, Toluca, CP 50000", Q_ADDRESS, stage="profiling",
            domicilio="Av. Morelos 245, Col. Centro, Toluca", codigo_postal="50000"),
        say("soy empleada y gano 20 mil al mes", Q_INCOME, stage="profiling",
            situacion_laboral="empleado", ingreso_monto=20000, ingreso_periodicidad="mensual"),
        say("sí, adelante", Q_CONSENT, stage="profiling", consentimiento_buro=True),
        say("la primera", Q_OPTION, stage="simulation", intent="elegir_opcion", opcion_elegida=1),
    ]
