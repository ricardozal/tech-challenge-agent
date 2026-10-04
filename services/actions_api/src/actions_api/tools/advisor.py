"""escalate and the advisor tools (P4, FR-039 to FR-046, FR-050)."""

from actions_api.escalation import open_escalation, resolve_open_escalation
from actions_api.toolkit import HandlerContext, ToolRejected, tool
from actions_api.tools.gate import auto_gate
from contracts.actions import (
    EscalateInput,
    RejectCaseInput,
    RequestCorrectionInput,
    ReturnToAgentInput,
    RevokeOkInput,
    VerifyValidationManuallyInput,
)
from contracts.common import Actor, EscalationReason, RejectionReason, Stage, Status, ValidationOrigin, ValidationResult

AGENT_REASONS = {EscalationReason.client_requested_human, EscalationReason.sensitive_topic}


@tool("escalate")
def escalate(ctx: HandlerContext) -> None:
    data: EscalateInput = ctx.input
    if ctx.actor == Actor.agent and data.reason not in AGENT_REASONS:
        raise ToolRejected("invalid_input", "El agente solo escala por petición del cliente o tema sensible.",
                           {"allowed": sorted(r.value for r in AGENT_REASONS)})
    evidence = dict(data.evidence)
    if ctx.tool_context.evidence_message_id:
        evidence["message_id"] = ctx.tool_context.evidence_message_id
    open_escalation(ctx, data.reason, evidence=evidence, agent_note=data.agent_note)


def _back_to_agent(ctx: HandlerContext, resolution: dict) -> None:
    """Resolve the ticket and hand the case back; the attempt counter restarts after a human intervened."""
    resolve_open_escalation(ctx, resolution)
    ctx.state.attempts = {}
    ctx.set_status(Status.active)


@tool("request_correction")
def request_correction(ctx: HandlerContext) -> None:
    data: RequestCorrectionInput = ctx.input
    _back_to_agent(ctx, {"tool": "request_correction", "validation_key": data.validation_key,
                         "message_to_client": data.message_to_client})
    ctx.set_stage(Stage.documents)
    ctx.emit("correction_requested", validation_key=data.validation_key)


@tool("return_to_agent")
def return_to_agent(ctx: HandlerContext) -> None:
    data: ReturnToAgentInput = ctx.input
    _back_to_agent(ctx, {"tool": "return_to_agent", "note": data.note})


@tool("reject_case")
def reject_case(ctx: HandlerContext) -> None:
    data: RejectCaseInput = ctx.input
    reason = RejectionReason.advisor_rejected.value
    resolve_open_escalation(ctx, {"tool": "reject_case", "reason": data.reason})
    ctx.set_status(Status.rejected)
    ctx.decide("rejection", "rejected", reason, {"advisor_reason": data.reason})
    ctx.emit("case_rejected", reason=reason)
    ctx.result["reason"] = reason


@tool("verify_validation_manually")
def verify_validation_manually(ctx: HandlerContext) -> None:
    """The advisor vouches for one validation; the gate is still evaluated by the system (FR-045)."""
    data: VerifyValidationManuallyInput = ctx.input
    current = ctx.state.validations.get(data.validation_key)
    if current is None:
        raise ToolRejected("invalid_input", "No existe esa validación en el caso.",
                           {"validations": sorted(ctx.state.validations)})
    ctx.state.validations[data.validation_key] = current.model_copy(update={
        "result": ValidationResult.passed,
        "origin": ValidationOrigin.manual,
        "justification": data.justification,
        "evidence": [*current.evidence, *data.evidence],
        "attempt": current.attempt + 1,
        "policy_version": ctx.policy.policy_version,
        "at": ctx.now,
    })
    ctx.emit("validation_recorded", key=data.validation_key, validation_type=current.type.value,
             result=ValidationResult.passed.value, origin=ValidationOrigin.manual.value)
    auto_gate(ctx)


@tool("revoke_ok")
def revoke_ok(ctx: HandlerContext) -> None:
    """A revoked OK counts as a false OK in the report (FR-049, FR-050)."""
    data: RevokeOkInput = ctx.input
    ctx.decide("ok_revocation", "revoked", data.reason)
    ctx.emit("ok_revoked", reason=data.reason)
    open_escalation(ctx, EscalationReason.ok_revoked, evidence={"reason": data.reason})
