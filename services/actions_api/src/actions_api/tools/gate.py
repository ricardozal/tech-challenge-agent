"""evaluate_gate: the only tool that sets ok_for_lender (R-08, FR-036, FR-037)."""

from actions_api.escalation import resolve_open_escalation
from actions_api.rules.gate import evaluate
from actions_api.toolkit import HandlerContext, ToolRejected, tool
from contracts.common import Status


@tool("evaluate_gate")
def evaluate_gate(ctx: HandlerContext) -> None:
    decision = evaluate(ctx.state.validations)
    if not decision.passed:
        raise ToolRejected("gate_not_met", "Faltan validaciones aprobadas.", {"missing": decision.missing})
    resolve_open_escalation(ctx, {"tool": "evaluate_gate", "outcome": "gate_passed"})
    ctx.set_status(Status.ok_for_lender)
    ctx.decide("gate", "passed", inputs={"validations": sorted(ctx.state.validations)})
    ctx.emit("gate_passed")
    ctx.result["ok_for_lender"] = True


def auto_gate(ctx: HandlerContext) -> None:
    """Evaluated by the system every time validations change; only a passing gate runs the tool."""
    if ctx.case.status not in (Status.active, Status.escalated):
        return
    decision = evaluate(ctx.state.validations)
    if decision.passed:
        ctx.follow_up("evaluate_gate")
    else:
        ctx.emit("gate_failed", missing=decision.missing)
