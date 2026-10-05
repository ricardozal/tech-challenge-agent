"""Documents node against the compose (doc_intel and the gateway in LLM_MODE=fake) (P3)."""

import pytest

from tests.support.conversation import (
    Q_ID, Q_INCOME_PROOF, Q_INVOICE, Q_PROOF_OF_ADDRESS, converse, laura_to_documents, tools, upload,
)


@pytest.mark.req("FR-025")
def test_asks_for_the_four_documents_one_by_one(stack):
    case_id, turns = converse(stack, [
        *laura_to_documents(),
        upload("laura_identification", "identification"),
        upload("laura_payslip", "payslip"),
        upload("laura_proof_of_address", "proof_of_address"),
        upload("laura_invoice", "vehicle_invoice"),
    ])
    chosen, *docs = turns[-5:]

    assert chosen["reply"].endswith(Q_ID)
    assert [d["reply"].endswith(q) for d, q in zip(docs[:3], (Q_INCOME_PROOF, Q_PROOF_OF_ADDRESS, Q_INVOICE))] == [True] * 3
    assert all(tools(d) == ["submit_document"] for d in docs)
    # The acknowledgement is worded by the model (recorded answer); that each document passed is checked below.
    validations = stack["http"].get(f"{stack['actions']}/cases/{case_id}").json()["state"]["validations"]
    assert len(validations) == 9 and {v["result"] for v in validations.values()} == {"passed"}


@pytest.mark.req("FR-034")
def test_income_mismatch_names_the_document_the_field_and_asks_again(stack):
    _, turns = converse(stack, [
        *laura_to_documents(),
        upload("laura_identification", "identification"),
        upload("laura_payslip_low", "payslip"),
    ])
    reply = turns[-1]["reply"]
    assert "comprobante de ingresos" in reply
    # The wording comes from the model (recorded answer); the document, amounts and mismatch from the code.
    assert all(fact in reply for fact in ("comprobante de ingresos", "$14,000.00", "$20,000.00", "no coincide"))
    assert reply.endswith(Q_INCOME_PROOF)


@pytest.mark.req("FR-034")
def test_illegible_document_asks_for_a_better_photo(stack):
    _, turns = converse(stack, [*laura_to_documents(), upload("illegible_identification", "identification")])
    assert "no pude leer bien" in turns[-1]["reply"] and turns[-1]["reply"].endswith(Q_ID)


@pytest.mark.req("FR-032")
def test_invoice_of_another_holder_is_explained(stack):
    _, turns = converse(stack, [*laura_to_documents(), upload("laura_invoice_other_holder", "vehicle_invoice")])
    assert "la factura no está a tu nombre" in turns[-1]["reply"]
    assert turns[-1]["reply"].endswith(Q_INVOICE)


def test_wrong_document_type_is_pointed_out(stack):
    _, turns = converse(stack, [*laura_to_documents(), upload("laura_invoice", "identification")])
    assert "parece ser factura del auto, pero te pedí tu identificación" in turns[-1]["reply"]
    assert turns[-1]["reply"].endswith(Q_ID)
