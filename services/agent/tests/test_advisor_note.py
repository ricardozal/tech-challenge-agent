"""The advisor's correction request reaches the client on the next turn (US4/AC9, FR-044)."""

import uuid

import pytest

from scripts.seed_fixtures import seed_steps
from tests.support.conversation import Q_ID, converse, laura_to_documents, say, tools

NOTE = "Envía el recibo de nómina de la segunda quincena de septiembre."


@pytest.mark.req("FR-044")
def test_correction_requested_by_the_advisor_is_relayed_once(stack):
    http = stack["http"]
    case_id, turns = converse(stack, [
        *laura_to_documents(),
        say("prefiero que me atienda una persona", Q_ID, stage="documents", intent="pedir_humano"),
    ])
    assert turns[-1]["case"]["status"] == "escalated"

    case = http.get(f"{stack['actions']}/cases/{case_id}").json()
    advisor = http.post(
        f"{stack['actions']}/tools/request_correction",
        json={"context": {"case_id": case_id, "idempotency_key": f"adv-{uuid.uuid4()}",
                          "expected_version": case["version"]},
              "input": {"validation_key": "income", "message_to_client": NOTE}},
        headers={"X-Actor": "advisor"},
    )
    assert advisor.status_code == 200

    follow_up = [say("ok, ¿qué sigue?", None, stage="documents", intent="pregunta"),
                 say("va, ahorita lo busco", Q_ID, stage="documents", intent="otro")]
    seed_steps(follow_up)
    replies = []
    for step in follow_up:
        resp = http.post(f"{stack['agent']}/cases/{case_id}/messages", json={"text": step["say"]},
                         headers={"Idempotency-Key": f"t-{uuid.uuid4()}"})
        assert resp.status_code == 200, resp.text
        replies.append(resp.json())

    assert NOTE in replies[0]["reply"] and replies[0]["reply"].endswith(Q_ID)
    assert replies[0]["case"]["status"] == "active"
    assert NOTE not in replies[1]["reply"]  # delivered once
    assert tools(replies[0]) == []
    assert http.get(f"{stack['actions']}/cases/{case_id}").json()["state"]["pending_client_note"] is None
