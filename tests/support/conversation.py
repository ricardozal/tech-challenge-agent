"""Play a short conversation against the compose agent with fixtures seeded for its messages."""

import uuid

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


def say(text: str, question: str, stage: str = "eligibility", intent: str = "proporcionar_datos", **campos) -> dict:
    return {"say": text, "stage": stage, "question": question, "extract": {"intencion": intent, "campos": campos}}


def converse(stack: dict, steps: list[dict]) -> tuple[str, list[dict]]:
    seed_steps(steps)
    http = stack["http"]
    case_id = http.post(f"{stack['agent']}/cases").json()["case_id"]
    turns = []
    for step in steps:
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
