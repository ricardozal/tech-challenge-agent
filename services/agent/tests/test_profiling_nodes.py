"""Profiling and simulation nodes against the compose services (P2)."""

import pytest

from tests.support.conversation import (
    Q_ADDRESS, Q_CONSENT, Q_ID, Q_INCOME, Q_OPTION, converse, eligible_steps, say, tools,
)

ADDRESS = say("Av. Morelos 245, Col. Centro, Toluca, CP 50000", Q_ADDRESS, stage="profiling",
              domicilio="Av. Morelos 245, Col. Centro, Toluca", codigo_postal="50000")
INCOME = say("soy empleada y gano 20 mil al mes", Q_INCOME, stage="profiling",
             situacion_laboral="empleado", ingreso_monto=20000, ingreso_periodicidad="mensual")
CONSENT = say("sí, adelante", Q_CONSENT, stage="profiling", consentimiento_buro=True)


def laura(spare_key=True):
    return eligible_steps("Laura Méndez Rojas", "Volkswagen", "Jetta", 2019, spare_key)


@pytest.mark.req("FR-017")
def test_asks_address_income_and_consent_then_proposes_options(stack):
    _, turns = converse(stack, [*laura(), ADDRESS, INCOME, CONSENT])
    profiling = turns[-3:]

    assert turns[-4]["reply"].endswith(Q_ADDRESS)
    assert [t["reply"].endswith(q) for t, q in zip(profiling, (Q_INCOME, Q_CONSENT, Q_OPTION))] == [True] * 3
    assert tools(profiling[-1]) == ["record_bureau_consent", "run_credit_check", "simulate_options"]
    # The wording comes from the model (recorded answer); the amounts come from the code.
    assert all(fact in profiling[-1]["reply"] for fact in ("$90,000.00", "$4,932.63", "24 meses"))
    assert profiling[-1]["case"]["stage"] == "simulation"
    # the agent never asks the client how much they want
    assert not any("cuánto necesitas" in t["reply"] or "monto" in t["reply"].lower() for t in turns)


@pytest.mark.req("FR-024")
def test_other_amount_is_not_offered_and_a_proposed_option_is_selected(stack):
    _, turns = converse(stack, [
        *laura(), ADDRESS, INCOME, CONSENT,
        say("quiero 300 mil", Q_OPTION, stage="simulation", monto_solicitado=300000),
        say("la segunda", Q_OPTION, stage="simulation", intent="elegir_opcion", opcion_elegida=2),
    ])
    other, chosen = turns[-2], turns[-1]

    assert tools(other) == []
    assert "Solo puedo ofrecerte las opciones que te mostré" in other["reply"]
    assert other["reply"].endswith(Q_OPTION)
    assert tools(chosen) == ["select_option"]
    assert chosen["case"]["stage"] == "documents"
    assert "$67,500.00" in chosen["reply"] and chosen["reply"].endswith(Q_ID)


@pytest.mark.req("FR-022")
def test_options_show_the_key_cost_when_there_is_no_spare_key(stack):
    _, turns = converse(stack, [*laura(spare_key=False), ADDRESS, INCOME, CONSENT])
    assert "Recibes $88,150.00 (financiamos $90,000.00, que incluye $1,850.00 de la segunda llave)" in turns[-1]["reply"]


@pytest.mark.req("FR-018")
def test_refused_consent_is_explained_and_asked_again(stack):
    _, turns = converse(stack, [
        *laura(), ADDRESS, INCOME, say("no, no quiero que revisen mi buró", Q_CONSENT, stage="profiling",
                                       consentimiento_buro=False),
    ])
    assert "run_credit_check" not in tools(turns[-1])
    assert "es necesaria para continuar" in turns[-1]["reply"] and turns[-1]["reply"].endswith(Q_CONSENT)


@pytest.mark.req("FR-020")
def test_unemployed_client_gets_no_offer_without_being_asked_for_income_or_consent(stack):
    _, turns = converse(stack, [
        *laura(), ADDRESS,
        say("ahorita no tengo trabajo", Q_INCOME, stage="profiling", situacion_laboral="desempleado"),
    ])
    last = turns[-1]
    assert tools(last) == ["update_declared_data", "run_credit_check"]
    assert last["case"]["status"] == "rejected"
    assert "con tu perfil actual no tenemos una oferta disponible" in last["reply"]
    assert not last["reply"].endswith(Q_CONSENT)
