"""Eligibility node against the compose services with fake LLM fixtures (P1)."""

import pytest

from tests.support.conversation import Q_ADDRESS, Q_DEBT, Q_KEY, Q_NAME, Q_OWN, Q_VEHICLE, converse, say, tools

NAME = say("me llamo Laura Méndez Rojas", Q_NAME, nombre_completo="Laura Méndez Rojas")
VEHICLE = say("tengo un Jetta 2019 de Volkswagen", Q_VEHICLE, auto_marca="Volkswagen", auto_modelo="Jetta", auto_anio=2019)


@pytest.mark.req("FR-010")
def test_asks_name_first_then_vehicle_ownership_debt_and_spare_key(stack):
    case_id, turns = converse(stack, [
        NAME,
        VEHICLE,
        say("sí, está a mi nombre", Q_OWN, auto_a_nombre_propio=True),
        say("no debo nada", Q_DEBT, adeudos_vehiculo=False),
        say("sí tengo las dos llaves", Q_KEY, segunda_llave=True),
    ])

    assert [t["reply"].endswith(q) for t, q in zip(turns, (Q_VEHICLE, Q_OWN, Q_DEBT, Q_KEY, Q_ADDRESS))] == [True] * 5
    assert [tools(t) for t in turns[:4]] == [["update_declared_data"]] * 4
    assert tools(turns[4]) == ["update_declared_data", "evaluate_eligibility"]
    assert turns[4]["case"]["stage"] == "profiling"
    case = stack["http"].get(f"{stack['actions']}/cases/{case_id}").json()
    assert case["state"]["client"]["full_name"] == "Laura Méndez Rojas"


@pytest.mark.req("FR-015")
def test_ambiguous_answer_is_asked_again_without_deciding(stack):
    _, turns = converse(stack, [
        NAME,
        VEHICLE,
        say("lo maneja mi esposa", Q_OWN),  # the model returns null for ownership
    ])

    assert turns[-1]["reply"].endswith(Q_OWN)
    assert "evaluate_eligibility" not in tools(turns[-1])
    assert turns[-1]["case"]["status"] == "active"


@pytest.mark.req("FR-016")
def test_rejection_reply_states_the_reason_in_spanish(stack):
    _, turns = converse(stack, [
        NAME,
        VEHICLE,
        say("no, es de mi hermano", Q_OWN, auto_a_nombre_propio=False),
    ])

    assert turns[-1]["case"]["status"] == "rejected"
    assert "no está a tu nombre" in turns[-1]["reply"]


def test_spare_key_quote_is_explained_to_the_client(stack):
    _, turns = converse(stack, [
        NAME,
        VEHICLE,
        say("sí, es mío", Q_OWN, auto_a_nombre_propio=True),
        say("está liquidado", Q_DEBT, adeudos_vehiculo=False),
        say("perdí la segunda llave", Q_KEY, segunda_llave=False),
    ])

    assert turns[-1]["case"]["stage"] == "profiling"
    assert "$1850.00" in turns[-1]["reply"] and "plan de pagos" in turns[-1]["reply"]
