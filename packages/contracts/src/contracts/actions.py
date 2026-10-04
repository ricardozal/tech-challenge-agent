"""Case Actions API contract (contracts/actions-api.md)."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from contracts.common import DocumentType, Employment, EscalationReason, Outcome, Periodicity, Stage, Status


class ToolContext(BaseModel):
    case_id: UUID | None = None  # only create_case goes without it
    idempotency_key: str = Field(min_length=1, max_length=200)
    expected_version: int | None = None
    on_behalf_of: Literal["client"] | None = None
    evidence_message_id: str | None = None


class ToolCall(BaseModel):
    context: ToolContext
    input: dict[str, Any] = {}


class CaseRef(BaseModel):
    id: UUID
    stage: Stage
    status: Status
    version: int


class Rejection(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ToolResult(BaseModel):
    outcome: Outcome
    case: CaseRef | None = None
    result: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    rejection: Rejection | None = None
    policy_version: str | None = None


# --- Inputs, one per tool -----------------------------------------------------------------------


class NoInput(BaseModel):
    model_config = {"extra": "forbid"}


class CreateCaseInput(NoInput):
    pass


class AppendMessageInput(BaseModel):
    message_id: str
    author: Literal["client", "agent"]
    text: str
    intent: str | None = None


class UpdateDeclaredDataInput(BaseModel):
    """Only confirmed values; `None` means no change (FR-015)."""

    model_config = {"extra": "forbid"}

    full_name: str | None = None
    address: str | None = None
    postal_code: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    own_name: bool | None = None
    declared_debt: bool | None = None
    spare_key: bool | None = None
    employment: Employment | None = None
    income_amount: str | None = None  # decimal string
    income_currency: str | None = None
    income_periodicity: Periodicity | None = None


class EvaluateEligibilityInput(NoInput):
    pass


class RecordBureauConsentInput(BaseModel):
    consent: Literal[True]


class RunCreditCheckInput(NoInput):
    pass


class SimulateOptionsInput(NoInput):
    pass


class SelectOptionInput(BaseModel):
    option_id: str


class SubmitDocumentInput(BaseModel):
    requested_type: DocumentType
    filename: str
    mime_type: str = "image/png"
    content_base64: str


class EvaluateGateInput(NoInput):
    pass


class EscalateInput(BaseModel):
    reason: EscalationReason
    agent_note: str | None = None
    evidence: dict[str, Any] = {}


class CancelCaseInput(BaseModel):
    reason: str = "cliente_cancela"


class RequestCorrectionInput(BaseModel):
    validation_key: str
    message_to_client: str


class VerifyValidationManuallyInput(BaseModel):
    validation_key: str
    justification: str = Field(min_length=10)
    evidence: list[str] = Field(min_length=1)


class RejectCaseInput(BaseModel):
    reason: str = Field(min_length=3)


class ReturnToAgentInput(BaseModel):
    note: str = ""


class RevokeOkInput(BaseModel):
    reason: str = Field(min_length=3)


TOOL_INPUTS: dict[str, type[BaseModel]] = {
    "create_case": CreateCaseInput,
    "append_message": AppendMessageInput,
    "update_declared_data": UpdateDeclaredDataInput,
    "evaluate_eligibility": EvaluateEligibilityInput,
    "record_bureau_consent": RecordBureauConsentInput,
    "run_credit_check": RunCreditCheckInput,
    "simulate_options": SimulateOptionsInput,
    "select_option": SelectOptionInput,
    "submit_document": SubmitDocumentInput,
    "evaluate_gate": EvaluateGateInput,
    "escalate": EscalateInput,
    "cancel_case": CancelCaseInput,
    "request_correction": RequestCorrectionInput,
    "verify_validation_manually": VerifyValidationManuallyInput,
    "reject_case": RejectCaseInput,
    "return_to_agent": ReturnToAgentInput,
    "revoke_ok": RevokeOkInput,
}
