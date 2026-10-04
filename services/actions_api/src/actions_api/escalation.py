"""Escalation tickets: deterministic Spanish summary and suggested action (R-09)."""

from typing import Any
from uuid import uuid4

from actions_api import db
from actions_api.toolkit import HandlerContext
from contracts.case import Escalation
from contracts.common import EscalationReason, Status, ValidationResult

REASON_ES = {
    EscalationReason.mismatch_persisted: "un dato no coincide después de los intentos de corrección permitidos",
    EscalationReason.client_requested_human: "el cliente pidió hablar con una persona",
    EscalationReason.sensitive_topic: "el cliente mencionó un tema sensible",
    EscalationReason.provider_failure: "un proveedor externo no respondió tras los reintentos",
    EscalationReason.no_reference_value: "no hay valor de referencia para el auto declarado",
    EscalationReason.ok_revoked: "un asesor revocó el OK para financiera",
    EscalationReason.policy_unavailable: "la versión de política del caso no está disponible",
}

SUGGESTED_ACTION = {
    EscalationReason.mismatch_persisted: (
        "Revisar la evidencia de la validación fallida; verificarla manualmente con justificación, "
        "pedir una corrección concreta al cliente o rechazar el caso."
    ),
    EscalationReason.client_requested_human: "Contactar al cliente y continuar el caso o devolverlo al agente.",
    EscalationReason.sensitive_topic: (
        "Contactar al cliente con cuidado; no continuar el proceso hasta entender la situación."
    ),
    EscalationReason.provider_failure: "Reintentar la consulta más tarde y devolver el caso al agente.",
    EscalationReason.no_reference_value: (
        "Valuar el auto manualmente o rechazar el caso si no se puede valuar."
    ),
    EscalationReason.ok_revoked: "Revisar el motivo de la revocación y decidir corrección o rechazo.",
    EscalationReason.policy_unavailable: "Restaurar la versión de política del caso antes de continuar.",
}

STAGE_ES = {
    "eligibility": "elegibilidad",
    "profiling": "perfilamiento",
    "simulation": "simulación",
    "documents": "documentos",
}


def build_summary(ctx: HandlerContext, reason: EscalationReason) -> str:
    state = ctx.state
    parts = [f"Caso en etapa de {STAGE_ES.get(ctx.case.stage, ctx.case.stage)}. Motivo: {REASON_ES[reason]}."]
    if state.client.full_name:
        parts.append(f"Cliente: {state.client.full_name}.")
    v = state.vehicle
    if v.make or v.model or v.year:
        parts.append(f"Auto: {' '.join(str(x) for x in (v.make, v.model, v.year) if x)}.")
    failed = [val for val in state.validations.values() if val.result != ValidationResult.passed]
    if failed:
        listed = ", ".join(f"{val.key} ({val.result}, intento {val.attempt})" for val in failed)
        parts.append(f"Validaciones pendientes: {listed}.")
    return " ".join(parts)


def open_escalation(
    ctx: HandlerContext,
    reason: EscalationReason,
    evidence: dict[str, Any] | None = None,
    agent_note: str | None = None,
) -> Escalation:
    """Create the ticket and move the case to `escalated` (FR-042)."""
    escalation = Escalation(
        id=uuid4(),
        case_id=ctx.case.id,
        reason=reason,
        evidence=evidence or {},
        summary=build_summary(ctx, reason),
        suggested_action=SUGGESTED_ACTION[reason],
        agent_note=agent_note,
        status="open",
        created_at=ctx.now,
    )
    db.insert_escalation(ctx.conn, escalation)
    ctx.set_status(Status.escalated)
    ctx.state.open_escalation_id = escalation.id
    ctx.emit("escalated", reason=reason.value, escalation_id=str(escalation.id), by=ctx.actor.value)
    ctx.result["escalation_id"] = str(escalation.id)
    return escalation


def resolve_open_escalation(ctx: HandlerContext, resolution: dict[str, Any]) -> None:
    if ctx.state.open_escalation_id is None:
        return
    db.resolve_escalation(
        ctx.conn,
        ctx.state.open_escalation_id,
        {**resolution, "actor": ctx.actor.value},
        ctx.now,
    )
    ctx.emit("escalation_resolved", escalation_id=str(ctx.state.open_escalation_id), **resolution)
    ctx.state.open_escalation_id = None
