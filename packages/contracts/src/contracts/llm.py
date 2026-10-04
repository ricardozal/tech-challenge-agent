"""LLM Gateway contract (contracts/llm-gateway.md) and translation of LLM output to the domain.

The extraction schemas (eval/esquemas.json) keep Spanish keys because they are the contract with the
model and what `make eval` measures (R-01). `to_domain` is the single place that maps them to the
English names used everywhere else.
"""

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel

from contracts.common import DocumentType, Employment, Intent, Periodicity, Stage, Status
from contracts.documents import ExtractedField

SchemaName = Literal["mensaje", "documento"]


class ExtractRequest(BaseModel):
    schema_name: SchemaName
    stage: Stage | None = None
    agent_question: str | None = None
    text: str


class ExtractResponse(BaseModel):
    data: dict[str, Any]
    schema_name: SchemaName
    schema_version: int
    model: str
    mode: str
    fixture_hit: bool


class OcrRequest(BaseModel):
    content_base64: str
    mime_type: str = "image/png"


class OcrResponse(BaseModel):
    text: str
    model: str
    mode: str
    fixture_hit: bool


class ReplyRequest(BaseModel):
    stage: Stage
    status: Status
    facts: dict[str, Any] = {}
    next_question: str | None = None
    client_first_name: str | None = None  # null until the client gives their name


class ReplyResponse(BaseModel):
    text: str
    model: str
    mode: str
    fixture_hit: bool


# --- Fixture key (R-11) -------------------------------------------------------------------------

_SPACES = re.compile(r"\s+")


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return _SPACES.sub(" ", value.strip().lower())
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def fixture_key(task: str, schema_name: str | None, inputs: dict[str, Any]) -> str:
    """sha256 of the canonical request; shared by the gateway and scripts/seed_fixtures.py."""
    canonical = json.dumps(
        {"task": task, "schema_name": schema_name, "inputs": _normalize(inputs)},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- Message extraction → domain ----------------------------------------------------------------

INTENTS = {
    "proporcionar_datos": Intent.provide_data,
    "elegir_opcion": Intent.choose_option,
    "pregunta": Intent.question,
    "pedir_humano": Intent.request_human,
    "cancelar": Intent.cancel,
    "tema_sensible": Intent.sensitive_topic,
    "otro": Intent.other,
}

EMPLOYMENT = {
    "empleado": Employment.employed,
    "independiente": Employment.self_employed,
    "pensionado": Employment.retired,
    "desempleado": Employment.unemployed,
}

PERIODICITY = {
    "semanal": Periodicity.weekly,
    "quincenal": Periodicity.biweekly,
    "mensual": Periodicity.monthly,
}

MESSAGE_FIELDS = {
    "nombre_completo": "full_name",
    "domicilio": "address",
    "codigo_postal": "postal_code",
    "auto_a_nombre_propio": "own_name",
    "adeudos_vehiculo": "declared_debt",
    "segunda_llave": "spare_key",
    "auto_marca": "make",
    "auto_modelo": "model",
    "auto_anio": "year",
    "ingreso_monto": "income_amount",
    "ingreso_periodicidad": "income_periodicity",
    "situacion_laboral": "employment",
    "consentimiento_buro": "bureau_consent",
    "opcion_elegida": "chosen_option",
    "monto_solicitado": "requested_amount",
    "plazo_meses": "term_months",
}

DOCUMENT_TYPES = {
    "identificacion": DocumentType.identification,
    "recibo_nomina": DocumentType.payslip,
    "estado_cuenta": DocumentType.bank_statement,
    "comprobante_domicilio": DocumentType.proof_of_address,
    "factura_vehiculo": DocumentType.vehicle_invoice,
    "otro": DocumentType.other,
}

DOCUMENT_FIELDS = {
    "nombre_completo": "full_name",
    "curp": "curp",
    "domicilio": "address",
    "codigo_postal": "postal_code",
    "fecha_nacimiento": "birth_date",
    "vigencia": "valid_until",
    "empleador": "employer",
    "banco": "bank",
    "periodicidad": "periodicity",
    "periodo_inicio": "period_start",
    "periodo_fin": "period_end",
    "ingreso_bruto": "gross_income",
    "ingreso_neto": "net_income",
    "total_depositos": "total_deposits",
    "saldo_final": "closing_balance",
    "fecha_emision": "issue_date",
    "marca": "make",
    "modelo": "model",
    "anio": "year",
    "niv": "vin",
    "moneda": "currency",
}


class MessageExtraction(BaseModel):
    intent: Intent
    # English field name → value; only fields the model returned as non-null.
    fields: dict[str, Any]


def to_domain(data: dict[str, Any]) -> MessageExtraction:
    """Translate a `mensaje` extraction (Spanish keys and values) to the domain."""
    intent = INTENTS.get(str(data.get("intencion")), Intent.other)
    fields: dict[str, Any] = {}
    for es_key, value in (data.get("campos") or {}).items():
        en_key = MESSAGE_FIELDS.get(es_key)
        if en_key is None or value is None:
            continue
        if en_key == "employment":
            value = EMPLOYMENT.get(value)
        elif en_key == "income_periodicity":
            value = PERIODICITY.get(value)
        if value is not None:
            fields[en_key] = value
    return MessageExtraction(intent=intent, fields=fields)


def document_type_to_domain(value: str | None) -> DocumentType:
    return DOCUMENT_TYPES.get(str(value), DocumentType.other)


def document_fields_to_domain(fields: dict[str, ExtractedField]) -> dict[str, ExtractedField]:
    """Rename `documento` schema keys to English; values and confidence are unchanged."""
    out: dict[str, ExtractedField] = {}
    for es_key, field in fields.items():
        en_key = DOCUMENT_FIELDS.get(es_key)
        if en_key is None:
            continue
        if en_key == "periodicity" and isinstance(field.value, str):
            mapped = PERIODICITY.get(field.value)
            field = ExtractedField(value=mapped.value if mapped else None, confidence=field.confidence)
        out[en_key] = field
    return out
