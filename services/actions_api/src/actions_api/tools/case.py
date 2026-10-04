"""Base tools: create_case, append_message, update_declared_data, cancel_case."""

from decimal import Decimal, InvalidOperation

from actions_api.escalation import resolve_open_escalation
from actions_api.toolkit import HandlerContext, ToolRejected, tool
from contracts.actions import AppendMessageInput, CancelCaseInput, UpdateDeclaredDataInput
from contracts.case import MessageRef
from contracts.common import Intent, Stage, Status

CLIENT_FIELDS = ("full_name", "address", "postal_code")
VEHICLE_FIELDS = ("make", "model", "year", "own_name", "declared_debt", "spare_key")
DECLARED_FIELDS = ("employment", "income_amount", "income_currency", "income_periodicity")
INCOME_FIELDS = ("income_amount", "income_currency", "income_periodicity")


@tool("create_case", creates_case=True)
def create_case(ctx: HandlerContext) -> None:
    """Empty case in eligibility/active with the current policy version pinned (R-14, R-16)."""
    ctx.result["case_id"] = str(ctx.case.id)
    ctx.emit("case_created", policy_version=ctx.case.policy_version)


@tool("append_message")
def append_message(ctx: HandlerContext) -> None:
    data: AppendMessageInput = ctx.input
    intent = Intent(data.intent) if data.intent in Intent.__members__ else None
    ctx.state.messages.append(
        MessageRef(id=data.message_id, author=data.author, text=data.text, intent=intent, at=ctx.now)
    )
    ctx.result["messages"] = len(ctx.state.messages)


@tool("update_declared_data")
def update_declared_data(ctx: HandlerContext) -> None:
    """Store confirmed values only; `None` means no change (FR-010, FR-015, FR-017)."""
    data: UpdateDeclaredDataInput = ctx.input
    values = data.model_dump(exclude_none=True)
    if not values:
        raise ToolRejected("unconfirmed_data", "No hay datos confirmados para guardar.")
    source = ctx.tool_context.evidence_message_id or ctx.tool_context.idempotency_key
    state = ctx.state
    changed: list[str] = []

    if "income_amount" in values:
        try:
            values["income_amount"] = Decimal(values["income_amount"])
        except InvalidOperation:
            raise ToolRejected("invalid_input", "El monto de ingreso no es un número.") from None
        if values["income_amount"] <= 0:
            raise ToolRejected("invalid_input", "El monto de ingreso debe ser positivo.")

    for section, names in ((state.client, CLIENT_FIELDS), (state.vehicle, VEHICLE_FIELDS),
                           (state.declared, DECLARED_FIELDS)):
        for name in names:
            if name in values and getattr(section, name) != values[name]:
                if getattr(section, name) is not None:
                    changed.append(name)
                setattr(section, name, values[name])
                section.sources[name] = source

    ctx.result["updated"] = sorted(values)
    ctx.result["corrected"] = sorted(changed)

    # A corrected income invalidates profile and options: back to profiling (spec edge case).
    if any(name in changed for name in INCOME_FIELDS) and ctx.case.stage in (Stage.simulation, Stage.documents):
        state.profile = None
        state.options = []
        state.selected_option_id = None
        ctx.set_stage(Stage.profiling)
        ctx.decide("data_correction", "profile_invalidated", reason="income_corrected", inputs={"fields": changed})
        ctx.emit("declared_data_corrected", fields=changed, back_to=Stage.profiling.value)

    # A corrected name or address makes the dependent validations pending again (re-evaluated by
    # the documents tools with the stored documents).
    identity = [name for name in changed if name in CLIENT_FIELDS]
    if identity:
        prefixes = ("name@",) if identity == ["full_name"] else ("name@", "address@")
        stale = [key for key in state.validations if key.startswith(prefixes)]
        for key in stale:
            del state.validations[key]
        if stale:
            ctx.emit("revalidation_required", keys=sorted(stale))
            ctx.result["revalidation_required"] = sorted(stale)


@tool("cancel_case")
def cancel_case(ctx: HandlerContext) -> None:
    """Client cancels (through the agent) or advisor cancels; closes any open ticket (FR-046)."""
    data: CancelCaseInput = ctx.input
    resolve_open_escalation(ctx, {"tool": "cancel_case", "reason": data.reason})
    ctx.set_status(Status.cancelled)
    ctx.emit("case_cancelled", reason=data.reason)
