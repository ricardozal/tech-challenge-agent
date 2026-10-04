"""submit_document (P3, FR-025 to FR-035): store, read, validate. Never decides the gate here."""

import base64
import hashlib
from collections.abc import Callable
from datetime import date
from uuid import uuid4

from actions_api.config import Settings
from actions_api.escalation import open_escalation
from actions_api.providers.base import ProviderError, with_retries
from actions_api.providers.document_reader import DocumentReader
from actions_api.rules.documents import INCOME_PROOFS, validations_for
from actions_api.rules.matching import validate_address, validate_name
from actions_api.toolkit import HandlerContext, ToolRejected, tool
from contracts.actions import SubmitDocumentInput
from contracts.case import DocumentRecord, Validation
from contracts.common import DocumentType, EscalationReason, ValidationResult
from contracts.llm import document_fields_to_domain

# Called after validations change (the gate and N-attempt escalation are wired in US4).
POST_VALIDATION_HOOKS: list[Callable[[HandlerContext, list[Validation]], None]] = []


def today(ctx: HandlerContext) -> date:
    settings: Settings = ctx.services.extras["settings"]
    return settings.as_of_date or ctx.now.date()


def same_family(requested: DocumentType, detected: DocumentType) -> bool:
    return requested == detected or (requested in INCOME_PROOFS and detected in INCOME_PROOFS)


def record_validations(ctx: HandlerContext, validations: list[Validation]) -> None:
    """Store the latest result per key and count non-passed results per type (FR-034)."""
    state = ctx.state
    for v in validations:
        previous = state.validations.get(v.key)
        v.attempt = previous.attempt + 1 if previous else 1
        state.validations[v.key] = v
        if v.result != ValidationResult.passed:
            state.attempts[v.type] = state.attempts.get(v.type, 0) + 1
        ctx.emit("validation_recorded", key=v.key, type=v.type.value, result=v.result.value,
                 reason=v.detail.get("reason"))
    for hook in POST_VALIDATION_HOOKS:
        hook(ctx, validations)


@tool("submit_document")
def submit_document(ctx: HandlerContext) -> None:
    data: SubmitDocumentInput = ctx.input
    try:
        content = base64.b64decode(data.content_base64, validate=True)
    except ValueError:
        raise ToolRejected("invalid_input", "El documento no es base64 válido.") from None
    sha = hashlib.sha256(content).hexdigest()
    settings: Settings = ctx.services.extras["settings"]
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    (settings.documents_dir / sha).write_bytes(content)

    reader: DocumentReader = ctx.services.extras["document_reader"]
    try:
        read = with_retries(
            lambda: reader.extract(data.requested_type, data.mime_type, data.content_base64),
            ctx.policy.escalation.provider_retries,
        )
    except ProviderError:
        open_escalation(ctx, EscalationReason.provider_failure,
                        evidence={"provider": "doc_intel", "tool": ctx.tool_name, "document_sha256": sha})
        return

    record = DocumentRecord(
        id=uuid4(),
        requested_type=data.requested_type,
        detected_type=read.detected_type,
        sha256=sha,
        is_test_specimen=read.is_test_specimen,
        fields=document_fields_to_domain(read.fields),
        received_at=ctx.now,
    )
    ctx.state.documents.append(record)
    ctx.result.update(document_id=str(record.id), detected_type=record.detected_type.value,
                      is_test_specimen=record.is_test_specimen)
    ctx.emit("document_received", document_id=str(record.id), requested_type=data.requested_type.value,
             detected_type=record.detected_type.value)

    if not same_family(data.requested_type, record.detected_type):
        ctx.emit("document_type_unexpected", requested_type=data.requested_type.value,
                 detected_type=record.detected_type.value)
        ctx.result["unexpected_type"] = True
        return

    validations = validations_for(record, ctx.state, ctx.policy, today(ctx), ctx.now)
    record_validations(ctx, validations)
    ctx.result["validations"] = [
        {"key": v.key, "result": v.result.value, "detail": v.detail} for v in validations
    ]


def revalidate_identity(ctx: HandlerContext, changed: list[str]) -> list[str]:
    """Re-run name/address validations with the stored documents after the client corrects them."""
    latest: dict[str, DocumentRecord] = {}
    for doc in ctx.state.documents:
        if doc.detected_type == DocumentType.identification:
            latest["name@identification"] = doc
        elif doc.detected_type in INCOME_PROOFS:
            latest["name@income_proof"] = doc
        elif doc.detected_type == DocumentType.proof_of_address:
            latest["address@proof_of_address"] = doc
    validations = []
    for key, doc in latest.items():
        if key.startswith("name@") and "full_name" in changed:
            validations.append(validate_name(ctx.state.client, doc, key, ctx.policy, ctx.now))
        elif key.startswith("address@") and {"address", "postal_code"} & set(changed):
            validations.append(validate_address(ctx.state.client, doc, ctx.policy, ctx.now))
    if validations:
        record_validations(ctx, validations)
    return [v.key for v in validations]
