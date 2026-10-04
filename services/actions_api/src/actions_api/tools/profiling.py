"""Profiling and simulation tools (P2, FR-017 to FR-024)."""

from decimal import Decimal

from actions_api.escalation import escalate_as_system
from actions_api.providers.base import ProviderError, with_retries
from actions_api.providers.bureau import BureauProvider
from actions_api.rules.options import build_options
from actions_api.rules.profile import assign, can_have_offer
from actions_api.toolkit import HandlerContext, ToolRejected, tool
from contracts.actions import SelectOptionInput
from contracts.case import Profile
from contracts.common import EscalationReason, RejectionReason, Stage, Status

REQUIRED_FOR_CHECK = {
    "full_name": lambda s: s.client.full_name,
    "address": lambda s: s.client.address,
    "postal_code": lambda s: s.client.postal_code,
    "employment": lambda s: s.declared.employment,
    "income_amount": lambda s: s.declared.income_amount,
    "income_periodicity": lambda s: s.declared.income_periodicity,
}


@tool("record_bureau_consent")
def record_bureau_consent(ctx: HandlerContext) -> None:
    """Explicit consent, with the client's message as evidence (FR-018)."""
    message_id = ctx.tool_context.evidence_message_id
    if not message_id:
        raise ToolRejected("invalid_input", "El consentimiento requiere el mensaje del cliente como evidencia.")
    declared = ctx.state.declared
    declared.bureau_consent = True
    declared.bureau_consent_at = ctx.now
    declared.bureau_consent_message_id = message_id
    ctx.emit("bureau_consent_recorded", message_id=message_id)


@tool("run_credit_check")
def run_credit_check(ctx: HandlerContext) -> None:
    state = ctx.state
    employment = state.declared.employment
    if employment is not None and not can_have_offer(employment, ctx.policy):
        # No income proof is accepted for this situation: no offer, and no reason to query the bureau.
        _reject_no_offer(ctx, {"employment": employment})
        return
    if not state.declared.bureau_consent:
        raise ToolRejected("consent_required", "Falta el consentimiento explícito del cliente para consultar Buró.")
    missing = [name for name, get in REQUIRED_FOR_CHECK.items() if get(state) is None]
    if missing:
        raise ToolRejected("unconfirmed_data", "Faltan datos confirmados del cliente.", {"missing": missing})
    reference_value = state.vehicle.registry.reference_value if state.vehicle.registry else None
    if reference_value is None:
        raise ToolRejected("unconfirmed_data", "El auto no tiene valor de referencia.", {"missing": ["reference_value"]})

    bureau: BureauProvider = ctx.services.extras["bureau"]
    try:
        score = with_retries(lambda: bureau.score(state.client.full_name), ctx.policy.escalation.provider_retries)
    except ProviderError:
        ctx.decide("profile", "escalated", "provider_failure", {"provider": "bureau"})
        escalate_as_system(ctx, EscalationReason.provider_failure, {"provider": "bureau", "tool": ctx.tool_name})
        return

    decision = assign(score, state.declared.employment, reference_value, ctx.policy)
    if not decision.offer:
        state.profile = Profile(bureau_score=score, policy_version=ctx.policy.policy_version)
        _reject_no_offer(ctx, {"bureau_score": score, "employment": state.declared.employment})
        return

    band = decision.band
    state.profile = Profile(
        bureau_score=score,
        band=band.band,
        max_amount_profile=band.max_amount,
        annual_rate=band.annual_rate,
        standard_term_months=band.standard_term_months,
        max_financeable=decision.max_financeable,
        policy_version=ctx.policy.policy_version,
    )
    ctx.decide("profile", "assigned", inputs={"bureau_score": score, "band": band.band})
    ctx.emit("profile_assigned", band=band.band)
    ctx.set_stage(Stage.simulation)
    ctx.result.update(band=band.band, max_financeable=f"{decision.max_financeable:.2f}")


@tool("simulate_options")
def simulate_options(ctx: HandlerContext) -> None:
    """Options are computed by the system, never by the agent (FR-021 to FR-023)."""
    state = ctx.state
    profile = state.profile
    if profile is None or profile.max_financeable is None:
        raise ToolRejected("unconfirmed_data", "No hay un perfil asignado.", {"missing": ["profile"]})
    key_cost = state.key_quote.amount if state.key_quote else Decimal("0")
    options = build_options(
        profile.max_financeable, profile.annual_rate, profile.standard_term_months, key_cost, ctx.policy
    )
    if not options:
        _reject_no_offer(ctx, {"key_cost": str(key_cost), "max_financeable": str(profile.max_financeable)})
        return
    state.options = options
    state.selected_option_id = None
    ctx.decide("options", "proposed", inputs={"count": len(options), "key_cost": str(key_cost)})
    ctx.emit("options_simulated", count=len(options), key_included=bool(state.key_quote))
    ctx.result["options"] = [o.model_dump(mode="json") for o in options]


@tool("select_option")
def select_option(ctx: HandlerContext) -> None:
    data: SelectOptionInput = ctx.input
    if data.option_id not in {o.id for o in ctx.state.options}:
        raise ToolRejected(
            "invalid_input", "Solo se puede elegir una de las opciones propuestas.",
            {"proposed": [o.id for o in ctx.state.options]},
        )
    ctx.state.selected_option_id = data.option_id
    ctx.emit("option_selected", option_id=data.option_id)
    ctx.set_stage(Stage.documents)
    ctx.result["selected_option_id"] = data.option_id


def _reject_no_offer(ctx: HandlerContext, inputs: dict) -> None:
    reason = RejectionReason.no_offer_for_profile.value
    ctx.set_status(Status.rejected)
    ctx.decide("rejection", "rejected", reason, inputs)
    ctx.emit("case_rejected", reason=reason)
    ctx.result.update(reason=reason)
