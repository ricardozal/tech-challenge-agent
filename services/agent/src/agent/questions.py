"""Fixed Spanish questions per missing field (R-19).

The texts are deterministic on purpose: they are part of the LLM fixture key (R-11) and match the
questions of the evaluation set (eval/casos_eval.jsonl).
"""

import re
from dataclasses import dataclass

from contracts.case import CaseView
from contracts.common import DocumentType, Employment, Stage


@dataclass(frozen=True)
class Question:
    id: str
    fields: tuple[str, ...]  # case fields this question fills
    text: str


Q_NAME = Question("full_name", ("full_name",), "¿Me compartes tu nombre completo?")
Q_VEHICLE = Question("vehicle", ("make", "model", "year"), "¿Qué auto es? Dime marca, modelo y año.")
Q_OWN_NAME = Question("own_name", ("own_name",), "¿El auto está a tu nombre?")
Q_DEBT = Question("declared_debt", ("declared_debt",), "¿El auto tiene algún adeudo, crédito o gravamen?")
Q_SPARE_KEY = Question("spare_key", ("spare_key",), "¿Tienes la segunda llave del auto?")
Q_ADDRESS = Question("address", ("address", "postal_code"), "¿Cuál es tu domicilio, con código postal?")
Q_INCOME = Question(
    "income", ("employment", "income_amount", "income_periodicity"), "¿Cuál es tu situación laboral y cuánto ganas?"
)
Q_CONSENT = Question("bureau_consent", ("bureau_consent",), "¿Nos autorizas consultar tu historial en Buró de Crédito?")
Q_OPTION = Question("option", ("selected_option_id",), "¿Cuál opción prefieres?")

DOCUMENT_QUESTIONS = {
    DocumentType.identification: Question(
        "doc_identification", (), "Envíame una foto de tu identificación oficial (INE o pasaporte)."
    ),
    "income_proof": Question(
        "doc_income_proof", (), "Envíame tu comprobante de ingresos más reciente (recibo de nómina o estado de cuenta)."
    ),
    DocumentType.proof_of_address: Question(
        "doc_proof_of_address", (), "¿Me envías tu comprobante de domicilio?"
    ),
    DocumentType.vehicle_invoice: Question("doc_vehicle_invoice", (), "Envíame la factura del auto."),
}

STAGE_QUESTIONS: dict[Stage, tuple[Question, ...]] = {
    Stage.eligibility: (Q_NAME, Q_VEHICLE, Q_OWN_NAME, Q_DEBT, Q_SPARE_KEY),
    Stage.profiling: (Q_ADDRESS, Q_INCOME, Q_CONSENT),
    Stage.simulation: (Q_OPTION,),
}

INCOME_PROOF_TYPES = (DocumentType.payslip, DocumentType.bank_statement)


def _value(case: CaseView, field: str) -> object:
    state = case.state
    for section in (state.client, state.vehicle, state.declared):
        if field in type(section).model_fields:
            value = getattr(section, field)
            if field == "bureau_consent":
                return value or None
            return value
    if field == "selected_option_id":
        return state.selected_option_id
    return None


# An unemployed client has no income to prove and gets no offer: income and consent are not asked (FR-020).
NOT_NEEDED_WHEN_UNEMPLOYED = ("income_amount", "income_periodicity", "bureau_consent")


def _pending(case: CaseView, field: str) -> bool:
    if case.state.declared.employment == Employment.unemployed and field in NOT_NEEDED_WHEN_UNEMPLOYED:
        return False
    return _value(case, field) is None


def missing_fields(case: CaseView, stage: Stage | None = None) -> list[str]:
    stage = stage or case.stage
    return [f for q in STAGE_QUESTIONS.get(stage, ()) for f in q.fields if _pending(case, f)]


def next_question(case: CaseView) -> Question | None:
    """First question of the current stage whose fields are not all filled yet."""
    if case.stage == Stage.documents:
        return next_document_question(case)
    for question in STAGE_QUESTIONS.get(case.stage, ()):
        if any(_pending(case, f) for f in question.fields):
            return question
    return None


# Validation keys each document family must pass (mirrors the gate's required keys).
FAMILY_KEYS: dict[str, tuple[str, ...]] = {
    DocumentType.identification: ("name@identification", "validity@identification"),
    "income_proof": ("income", "income_proof_type", "name@income_proof", "validity@income_proof"),
    DocumentType.proof_of_address: ("address@proof_of_address", "validity@proof_of_address"),
    DocumentType.vehicle_invoice: ("vehicle_ownership",),
}


def family(doc_type: str) -> str:
    return "income_proof" if doc_type in INCOME_PROOF_TYPES else doc_type


def missing_documents(case: CaseView) -> list[str]:
    """Families whose validations are not all passed yet, in the order the agent asks for them."""
    validations = case.state.validations
    return [
        fam for fam, keys in FAMILY_KEYS.items()
        if not all(k in validations and validations[k].result == "passed" for k in keys)
    ]


def document_question(doc_type: str) -> Question:
    return DOCUMENT_QUESTIONS[family(doc_type)]


def next_document_question(case: CaseView) -> Question | None:
    needed = missing_documents(case)
    return DOCUMENT_QUESTIONS[needed[0]] if needed else None


_MARKS = re.compile(r"[¿?¡!.,:;]")


def _plain(text: str) -> str:
    return " ".join(_MARKS.sub(" ", text).lower().split())


def end_with_question(reply: str, question: str | None) -> str:
    """The question asked is the code's decision (Principle II): the reply ends with its exact text.

    The real model sometimes rewrites its punctuation or case (e.g. "¿el auto está a tu nombre?" or
    "¿Envíame tu identificación?"); a trailing variant is replaced by the exact question, and a reply
    without it gets the question appended.
    """
    reply = reply.strip()
    if not question or reply.endswith(question):
        return reply
    target = _plain(question)
    for start in range(len(reply)):
        if (start == 0 or not reply[start - 1].isalnum()) and _plain(reply[start:]) == target:
            return (reply[:start].rstrip() + " " + question).strip()
    return f"{reply} {question}"

