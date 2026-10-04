"""Play a short conversation against the compose agent with fixtures seeded for its messages."""

import uuid

from scripts.seed_fixtures import seed_steps

Q_NAME = "¿Me compartes tu nombre completo?"
Q_VEHICLE = "¿Qué auto es? Dime marca, modelo y año."
Q_OWN = "¿El auto está a tu nombre?"
Q_DEBT = "¿El auto tiene algún adeudo, crédito o gravamen?"
Q_KEY = "¿Tienes la segunda llave del auto?"
Q_ADDRESS = "¿Cuál es tu domicilio, con código postal?"


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
