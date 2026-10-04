"""Permission matrix actor × (stage, status) × tool (contracts/actions-api.md, FR-004).

Each rule lists the actors allowed to call the tool and, per actor, the (status, stage) pairs in
which the call is valid. `None` as stage means "any stage".
"""

from dataclasses import dataclass

from contracts.case import CaseView
from contracts.common import Actor, Stage, Status

A, D, S = Actor.agent, Actor.advisor, Actor.system
ANY = None

Where = tuple[Status, Stage | None]


@dataclass(frozen=True)
class Rule:
    where: dict[Actor, tuple[Where, ...]]


def _all_stages(*statuses: Status) -> tuple[Where, ...]:
    return tuple((status, ANY) for status in statuses)


ACTIVE_OR_ESCALATED = _all_stages(Status.active, Status.escalated)

MATRIX: dict[str, Rule] = {
    # create_case has no case yet; only the actor is checked.
    "create_case": Rule({A: ()}),
    "append_message": Rule({A: _all_stages(*Status)}),
    "update_declared_data": Rule({A: _all_stages(Status.active)}),
    "evaluate_eligibility": Rule({A: ((Status.active, Stage.eligibility),)}),
    "record_bureau_consent": Rule({A: ((Status.active, Stage.profiling),)}),
    "run_credit_check": Rule({A: ((Status.active, Stage.profiling),)}),
    "simulate_options": Rule({A: ((Status.active, Stage.simulation),)}),
    "select_option": Rule({A: ((Status.active, Stage.simulation),)}),
    "submit_document": Rule({A: ((Status.active, Stage.documents),)}),
    "evaluate_gate": Rule(
        {
            A: ((Status.active, Stage.documents),),
            D: ((Status.active, Stage.documents), (Status.escalated, ANY)),
            S: ((Status.active, Stage.documents), (Status.escalated, ANY)),
        }
    ),
    "escalate": Rule({A: _all_stages(Status.active), D: _all_stages(Status.active), S: _all_stages(Status.active)}),
    # The client may cancel even while escalated; the agent executes it on their behalf (FR-043, FR-046).
    "cancel_case": Rule({A: ACTIVE_OR_ESCALATED, D: ACTIVE_OR_ESCALATED}),
    "request_correction": Rule({D: _all_stages(Status.escalated)}),
    "verify_validation_manually": Rule({D: _all_stages(Status.escalated)}),
    "reject_case": Rule({D: _all_stages(Status.escalated)}),
    "return_to_agent": Rule({D: _all_stages(Status.escalated)}),
    "revoke_ok": Rule({D: _all_stages(Status.ok_for_lender)}),
}

# Tools that still make sense on a closed case.
_ALLOWED_WHEN_CLOSED = {"append_message", "revoke_ok"}
_CLOSED = {Status.ok_for_lender, Status.rejected, Status.cancelled}


def check(actor: Actor, case: CaseView | None, tool: str) -> str | None:
    """Return a rejection code (`forbidden`, `case_closed`) or None when the call is allowed."""
    rule = MATRIX.get(tool)
    if rule is None or actor not in rule.where:
        return "forbidden"
    if case is None:
        return None
    if case.status in _CLOSED and tool not in _ALLOWED_WHEN_CLOSED:
        return "case_closed"
    for status, stage in rule.where[actor]:
        if case.status == status and (stage is ANY or case.stage == stage):
            return None
    return "forbidden"
