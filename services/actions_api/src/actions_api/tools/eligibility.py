"""evaluate_eligibility (P1, FR-011 to FR-016)."""

from actions_api.escalation import open_escalation
from actions_api.providers.base import ProviderError, with_retries
from actions_api.providers.key_quote import KeyQuoteProvider
from actions_api.providers.vehicle_registry import VehicleRegistryProvider
from actions_api.rules.eligibility import Outcome, evaluate
from actions_api.toolkit import HandlerContext, ToolRejected, tool
from contracts.case import KeyQuote, VehicleRegistry
from contracts.common import EscalationReason, Stage, Status


@tool("evaluate_eligibility")
def evaluate_eligibility(ctx: HandlerContext) -> None:
    vehicle = ctx.state.vehicle
    decision = evaluate(vehicle, vehicle.registry, ctx.policy)

    if decision.outcome == Outcome.needs_registry:
        if not ctx.state.client.full_name:
            raise ToolRejected("unconfirmed_data", "Falta el nombre del cliente.", {"missing": ["full_name"]})
        registry: VehicleRegistryProvider = ctx.services.extras["vehicle_registry"]
        try:
            record = with_retries(
                lambda: registry.lookup(ctx.state.client.full_name, vehicle.make, vehicle.model, vehicle.year),
                ctx.policy.escalation.provider_retries,
            )
        except ProviderError:
            _provider_failure(ctx, "vehicle_registry")
            return
        vehicle.registry = VehicleRegistry(lien=record.lien, reference_value=record.reference_value, checked_at=ctx.now)
        decision = evaluate(vehicle, vehicle.registry, ctx.policy)

    if decision.outcome == Outcome.incomplete:
        raise ToolRejected("unconfirmed_data", "Faltan respuestas confirmadas del cliente.", {"missing": decision.missing})

    if decision.outcome == Outcome.rejected:
        ctx.set_status(Status.rejected)
        ctx.decide("eligibility", "rejected", decision.rejection_reason, {"origin": decision.origin})
        ctx.emit("vehicle_rejected", reason=decision.rejection_reason, origin=decision.origin)
        ctx.result.update(eligible=False, reason=decision.rejection_reason, origin=decision.origin)
        return

    if decision.outcome == Outcome.no_reference_value:
        ctx.decide("eligibility", "escalated", "no_reference_value")
        open_escalation(ctx, EscalationReason.no_reference_value, evidence={"vehicle": vehicle.model_dump(mode="json")})
        return

    if decision.needs_key_quote:
        quotes: KeyQuoteProvider = ctx.services.extras["key_quote"]
        try:
            quote = with_retries(
                lambda: quotes.quote(vehicle.make, vehicle.model, vehicle.year), ctx.policy.escalation.provider_retries
            )
        except ProviderError:
            _provider_failure(ctx, "key_quote")
            return
        ctx.state.key_quote = KeyQuote(
            amount=quote.amount, provider_quote_id=quote.quote_id, quoted_at=ctx.now,
            policy_version=ctx.policy.policy_version,
        )
        ctx.emit("key_quoted", amount=f"{quote.amount:.2f}", quote_id=quote.quote_id)
        ctx.result["key_quote"] = f"{quote.amount:.2f}"

    ctx.decide("eligibility", "eligible", inputs={"needs_key_quote": decision.needs_key_quote})
    ctx.set_stage(Stage.profiling)
    ctx.result["eligible"] = True


def _provider_failure(ctx: HandlerContext, provider: str) -> None:
    ctx.decide("eligibility", "escalated", "provider_failure", {"provider": provider})
    open_escalation(ctx, EscalationReason.provider_failure, evidence={"provider": provider, "tool": ctx.tool_name})
