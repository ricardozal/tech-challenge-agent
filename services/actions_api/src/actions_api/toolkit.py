"""`@tool` decorator and execution pipeline (R-05).

One transaction per call: lock → idempotency → load case → expected version → permissions →
policy → input validation → handler → save (version + 1) → audit → follow-ups → idempotency.
Rejected calls are audited and stored for idempotency too, without touching the case.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from pydantic import BaseModel, ValidationError

from actions_api import db, permissions
from actions_api.policy import Policy, PolicyRegistry, PolicyUnavailable
from contracts.actions import TOOL_INPUTS, CaseRef, Rejection, ToolCall, ToolContext, ToolResult
from contracts.case import CaseState, CaseView, Decision
from contracts.common import Actor, Outcome, Stage, Status

HTTP_STATUS = {
    "forbidden": 403,
    "not_found": 404,
    "version_conflict": 409,
    "idempotency_mismatch": 409,
    "case_closed": 409,
    "gate_not_met": 409,
    "policy_unavailable": 409,
    "invalid_input": 422,
    "consent_required": 422,
    "unconfirmed_data": 422,
}

MESSAGES = {
    "forbidden": "La acción no está permitida para este actor en la etapa actual del caso.",
    "not_found": "El caso no existe.",
    "version_conflict": "El caso cambió desde la versión indicada; vuelve a leerlo e intenta de nuevo.",
    "idempotency_mismatch": "La llave de idempotencia ya se usó con otra solicitud.",
    "case_closed": "El caso está cerrado y no admite más acciones.",
    "policy_unavailable": "La versión de política del caso no está disponible.",
    "invalid_input": "La entrada de la acción no es válida.",
}


class ToolRejected(Exception):
    """Raised by a handler to reject the call without changing the case."""

    def __init__(self, code: str, message: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.message = message or MESSAGES.get(code, code)
        self.details = details or {}


@dataclass
class Services:
    """Dependencies handlers may use (providers, document client, settings)."""

    policies: PolicyRegistry
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class HandlerContext:
    conn: psycopg.Connection
    case: CaseView
    input: BaseModel
    policy: Policy
    now: datetime
    actor: Actor
    tool_context: ToolContext
    tool_name: str
    services: Services
    events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    followups: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    @property
    def state(self) -> CaseState:
        return self.case.state

    def emit(self, event_type: str, **data: Any) -> None:
        self.events.append({"type": event_type, **data})

    def decide(self, kind: str, result: str, reason: str | None = None, inputs: dict | None = None) -> None:
        self.state.decisions.append(
            Decision(
                kind=kind,
                result=result,
                reason=reason,
                actor=self.actor,
                inputs=inputs or {},
                policy_version=self.policy.policy_version,
                at=self.now,
            )
        )

    def follow_up(self, tool: str, tool_input: dict[str, Any] | None = None) -> None:
        """Run another tool as `system` right after this one, as a separate audited action (R-08)."""
        self.followups.append((tool, tool_input or {}))

    def set_stage(self, stage: Stage) -> None:
        self.case.stage = stage

    def set_status(self, status: Status) -> None:
        self.case.status = status


Handler = Callable[[HandlerContext], None]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    handler: Handler
    creates_case: bool = False


REGISTRY: dict[str, ToolSpec] = {}


def tool(name: str, *, creates_case: bool = False) -> Callable[[Handler], Handler]:
    if name not in TOOL_INPUTS:
        raise ValueError(f"unknown tool {name!r}; add its input model to contracts.actions")

    def register(handler: Handler) -> Handler:
        REGISTRY[name] = ToolSpec(name=name, handler=handler, creates_case=creates_case)
        return handler

    return register


def new_case(policy: Policy, now: datetime) -> CaseView:
    return CaseView(
        id=uuid4(),
        stage=Stage.eligibility,
        status=Status.active,
        version=0,
        policy_version=policy.policy_version,
        created_at=now,
        updated_at=now,
        state=CaseState(),
    )


def execute(
    conn: psycopg.Connection,
    services: Services,
    name: str,
    actor: Actor,
    call: ToolCall,
    now: datetime | None = None,
) -> tuple[int, ToolResult]:
    """Run one tool call inside the caller's transaction. Returns (http_status, result)."""
    now = now or datetime.now(UTC)
    ctx_in = call.context
    spec = REGISTRY.get(name)
    if spec is None:
        return 404, _rejection("not_found", None, None, message=f"La tool {name!r} no existe.")

    scope = "global" if spec.creates_case else str(ctx_in.case_id)
    if not spec.creates_case and ctx_in.case_id is None:
        return 422, _rejection("invalid_input", None, None, message="Falta case_id.")
    db.lock_key(conn, scope if not spec.creates_case else f"create:{ctx_in.idempotency_key}")

    request_hash = _request_hash(name, actor, call)
    stored = db.get_idempotency(conn, scope, ctx_in.idempotency_key)
    if stored is not None:
        if stored["request_hash"] == request_hash:
            return stored["http_status"], ToolResult.model_validate(stored["response"])
        return _reject(conn, None, name, actor, call, now, "idempotency_mismatch", store=False)

    if spec.creates_case:
        policy = services.policies.current()
        case: CaseView | None = new_case(policy, now)
        before = None
    else:
        case = db.load_case(conn, ctx_in.case_id, for_update=True)
        if case is None:
            return 404, _rejection("not_found", None, None)
        before = case.model_copy(deep=True)
        if ctx_in.expected_version is None:
            return _reject(conn, before, name, actor, call, now, "invalid_input", message="Falta expected_version.")
        if ctx_in.expected_version != case.version:
            return _reject(
                conn, before, name, actor, call, now, "version_conflict",
                details={"expected_version": ctx_in.expected_version, "current_version": case.version},
            )

    code = permissions.check(actor, None if spec.creates_case else case, name)
    if code:
        return _reject(conn, before, name, actor, call, now, code)

    try:
        policy = services.policies.get(case.policy_version)
    except PolicyUnavailable:
        return _reject(conn, before, name, actor, call, now, "policy_unavailable")

    try:
        tool_input = TOOL_INPUTS[name].model_validate(call.input)
    except ValidationError as exc:
        return _reject(
            conn, before, name, actor, call, now, "invalid_input",
            details={"errors": json.loads(exc.json(include_url=False))},
        )

    hctx = HandlerContext(
        conn=conn,
        case=case,
        input=tool_input,
        policy=policy,
        now=now,
        actor=actor,
        tool_context=ctx_in,
        tool_name=name,
        services=services,
    )
    try:
        spec.handler(hctx)
    except ToolRejected as rej:
        return _reject(conn, before, name, actor, call, now, rej.code, message=rej.message, details=rej.details)

    case.version += 1
    case.updated_at = now
    if spec.creates_case:
        db.insert_case(conn, case)
    else:
        db.update_case(conn, case)

    db.insert_audit(
        conn,
        _audit_entry(before, case, name, actor, call, now, Outcome.accepted, None, hctx.result, hctx.events, policy),
    )

    status, result = 200, ToolResult(
        outcome=Outcome.accepted,
        case=_ref(case),
        result=hctx.result,
        events=hctx.events,
        policy_version=policy.policy_version,
    )

    for i, (followup, followup_input) in enumerate(hctx.followups):
        sub_call = ToolCall(
            context=ToolContext(
                case_id=case.id,
                idempotency_key=f"{ctx_in.idempotency_key}>{i}:{followup}",
                expected_version=result.case.version,
            ),
            input=followup_input,
        )
        _, sub = execute(conn, services, followup, Actor.system, sub_call, now)
        result.result.setdefault("followups", []).append(
            {
                "tool": followup,
                "outcome": sub.outcome.value,
                "rejection": sub.rejection.model_dump() if sub.rejection else None,
                "result": sub.result,
            }
        )
        result.events.extend(sub.events)
        if sub.case is not None:
            result.case = sub.case

    db.put_idempotency(
        conn, scope, ctx_in.idempotency_key, name, request_hash, status, result.model_dump(mode="json")
    )
    return status, result


# --- helpers -------------------------------------------------------------------------------------


def _request_hash(name: str, actor: Actor, call: ToolCall) -> str:
    payload = {
        "tool": name,
        "actor": actor,
        "context": call.context.model_dump(mode="json", exclude={"idempotency_key"}),
        "input": call.input,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _ref(case: CaseView) -> CaseRef:
    return CaseRef(id=case.id, stage=case.stage, status=case.status, version=case.version)


def _rejection(
    code: str, case: CaseView | None, policy_version: str | None, message: str | None = None, details=None
) -> ToolResult:
    return ToolResult(
        outcome=Outcome.rejected,
        case=_ref(case) if case else None,
        rejection=Rejection(code=code, message=message or MESSAGES.get(code, code), details=details or {}),
        policy_version=policy_version,
    )


def _reject(
    conn: psycopg.Connection,
    case: CaseView | None,
    name: str,
    actor: Actor,
    call: ToolCall,
    now: datetime,
    code: str,
    *,
    message: str | None = None,
    details: dict[str, Any] | None = None,
    store: bool = True,
) -> tuple[int, ToolResult]:
    policy_version = case.policy_version if case else None
    result = _rejection(code, case, policy_version, message, details)
    db.insert_audit(
        conn,
        _audit_entry(case, None, name, actor, call, now, Outcome.rejected, code, result.rejection.model_dump(), [], None,
                     policy_version=policy_version),
    )
    status = HTTP_STATUS.get(code, 400)
    if store and case is not None:
        db.put_idempotency(
            conn, str(case.id), call.context.idempotency_key, name, _request_hash(name, actor, call), status,
            result.model_dump(mode="json"),
        )
    return status, result


def _sanitize_input(tool_input: dict[str, Any]) -> dict[str, Any]:
    """Never store document bytes in the audit log; keep their hash instead."""
    clean = dict(tool_input)
    if "content_base64" in clean:
        content = str(clean.pop("content_base64"))
        clean["content_sha256_of_base64"] = hashlib.sha256(content.encode()).hexdigest()
    return clean


def _audit_entry(
    before: CaseView | None,
    after: CaseView | None,
    name: str,
    actor: Actor,
    call: ToolCall,
    now: datetime,
    outcome: Outcome,
    rejection_code: str | None,
    result: dict[str, Any],
    events: list[dict[str, Any]],
    policy: Policy | None,
    policy_version: str | None = None,
) -> dict[str, Any]:
    case_id: UUID | None = (after or before).id if (after or before) else call.context.case_id
    return {
        "case_id": case_id,
        "at": now,
        "actor": actor,
        "on_behalf_of": call.context.on_behalf_of,
        "tool": name,
        "stage_before": before.stage if before else None,
        "status_before": before.status if before else None,
        "stage_after": after.stage if after else None,
        "status_after": after.status if after else None,
        "idempotency_key": call.context.idempotency_key,
        "expected_version": call.context.expected_version,
        "case_version_after": after.version if after else None,
        "outcome": outcome,
        "rejection_code": rejection_code,
        "input": {
            **_sanitize_input(call.input),
            **({"evidence_message_id": call.context.evidence_message_id} if call.context.evidence_message_id else {}),
        },
        "result": result,
        "events": events,
        "policy_version": policy.policy_version if policy else policy_version,
    }
