"""Router: escalation and cancellation come from the classified intent, never from reply text (P4)."""

import pytest

from tests.support.conversation import Q_ADDRESS, Q_INCOME, Q_NAME, converse, eligible_steps, say, tools


def to_profiling():
    return eligible_steps("Laura Méndez Rojas", "Volkswagen", "Jetta", 2019)


@pytest.mark.req("FR-039")
def test_asking_for_a_person_escalates_in_any_stage(stack):
    case_id, turns = converse(stack, [
        *to_profiling(),
        say("prefiero hablar con una persona de verdad", Q_ADDRESS, stage="profiling", intent="pedir_humano"),
    ])
    assert tools(turns[-1]) == ["escalate"]
    assert turns[-1]["case"]["status"] == "escalated"
    assert "asesor" in turns[-1]["reply"]
    ticket = [t for t in stack["http"].get(f"{stack['actions']}/escalations").json() if t["case_id"] == case_id][-1]
    assert ticket["reason"] == "client_requested_human"


@pytest.mark.req("FR-040")
def test_sensitive_topic_is_escalated_without_trying_to_solve_it(stack):
    _, turns = converse(stack, [
        *to_profiling(),
        say("mi ex pareja me está obligando a sacar este préstamo", Q_ADDRESS, stage="profiling", intent="tema_sensible"),
    ])
    assert tools(turns[-1]) == ["escalate"]
    assert "un asesor te atienda personalmente" in turns[-1]["reply"]
    assert not turns[-1]["reply"].endswith("?")  # no further questions to the client


@pytest.mark.req("FR-046")
def test_cancel_intent_cancels_the_case(stack):
    _, turns = converse(stack, [
        *to_profiling(),
        say("ya no quiero seguir, gracias", Q_ADDRESS, stage="profiling", intent="cancelar"),
    ])
    assert tools(turns[-1]) == ["cancel_case"]
    assert turns[-1]["case"]["status"] == "cancelled"


@pytest.mark.req("FR-043")
def test_after_escalation_the_agent_only_records_messages(stack):
    _, turns = converse(stack, [
        *to_profiling(),
        say("quiero hablar con un asesor", Q_ADDRESS, stage="profiling", intent="pedir_humano"),
        say("Av. Morelos 245, Col. Centro, Toluca, CP 50000", None, stage="profiling",
            domicilio="Av. Morelos 245, Col. Centro, Toluca", codigo_postal="50000"),
    ])
    assert tools(turns[-1]) == []
    assert turns[-1]["case"] == {**turns[-2]["case"], "version": turns[-1]["case"]["version"]}
    assert not turns[-1]["reply"].endswith(Q_INCOME)


@pytest.mark.req("FR-001")
def test_message_in_another_language_or_off_topic_gets_a_spanish_reply_back_to_the_stage(stack):
    _, turns = converse(stack, [
        say("Hi! How much money can you lend me?", Q_NAME, intent="pregunta"),
        say("¿quién ganó el partido de ayer?", Q_NAME, intent="otro"),
    ])
    for turn in turns:
        assert tools(turn) == []  # nothing is decided from an off-topic message
        assert turn["case"] == {**turns[0]["case"], "version": turn["case"]["version"]}
        assert turn["reply"].endswith(Q_NAME)  # back to the current stage question, in Spanish
        assert "money" not in turn["reply"].lower()
