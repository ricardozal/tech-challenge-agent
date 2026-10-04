"""Permission matrix actor × stage × tool (pure)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from actions_api.permissions import check
from contracts.case import CaseState, CaseView
from contracts.common import Actor, Stage, Status


def case(stage=Stage.eligibility, status=Status.active) -> CaseView:
    now = datetime.now(UTC)
    return CaseView(id=uuid4(), stage=stage, status=status, version=1, policy_version="v", created_at=now,
                    updated_at=now, state=CaseState())


@pytest.mark.req("FR-004")
@pytest.mark.parametrize(
    ("actor", "tool", "stage", "status", "expected"),
    [
        (Actor.agent, "evaluate_eligibility", Stage.eligibility, Status.active, None),
        (Actor.agent, "evaluate_eligibility", Stage.profiling, Status.active, "forbidden"),
        (Actor.agent, "run_credit_check", Stage.profiling, Status.active, None),
        (Actor.agent, "submit_document", Stage.simulation, Status.active, "forbidden"),
        (Actor.advisor, "update_declared_data", Stage.eligibility, Status.active, "forbidden"),
        (Actor.agent, "verify_validation_manually", Stage.documents, Status.escalated, "forbidden"),
        (Actor.advisor, "verify_validation_manually", Stage.documents, Status.escalated, None),
        (Actor.advisor, "verify_validation_manually", Stage.documents, Status.active, "forbidden"),
        (Actor.agent, "revoke_ok", Stage.documents, Status.ok_for_lender, "forbidden"),
        (Actor.advisor, "revoke_ok", Stage.documents, Status.ok_for_lender, None),
        (Actor.agent, "update_declared_data", Stage.documents, Status.rejected, "case_closed"),
        (Actor.agent, "append_message", Stage.documents, Status.rejected, None),
    ],
)
def test_matrix(actor, tool, stage, status, expected):
    assert check(actor, case(stage, status), tool) == expected


@pytest.mark.req("FR-043")
def test_escalated_case_allows_the_agent_only_messages_and_cancellation():
    escalated = case(Stage.documents, Status.escalated)
    assert check(Actor.agent, escalated, "append_message") is None
    assert check(Actor.agent, escalated, "cancel_case") is None
    for tool in ("update_declared_data", "submit_document", "evaluate_gate", "escalate", "select_option"):
        assert check(Actor.agent, escalated, tool) == "forbidden", tool
