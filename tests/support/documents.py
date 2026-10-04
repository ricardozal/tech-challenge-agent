"""Builders of domain documents for rule and tool tests."""

from datetime import UTC, date, datetime
from uuid import uuid4

from contracts.case import ClientData, DocumentRecord
from contracts.common import DocumentType
from contracts.documents import ExtractedField

TODAY = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 12, tzinfo=UTC)
LAURA = ClientData(full_name="Laura Méndez Rojas", address="Av. Morelos 245, Col. Centro, Toluca", postal_code="50000")


def doc(doc_type: DocumentType, confidence: float = 0.95, **fields) -> DocumentRecord:
    return DocumentRecord(
        id=uuid4(),
        requested_type=doc_type,
        detected_type=doc_type,
        sha256="0" * 64,
        is_test_specimen=True,
        fields={k: ExtractedField(value=v, confidence=confidence if v is not None else 0.0) for k, v in fields.items()},
        received_at=NOW,
    )


def payslip(net=10000, periodicity="biweekly", currency="MXN", name="LAURA MÉNDEZ ROJAS", **kw) -> DocumentRecord:
    return doc(DocumentType.payslip, full_name=name, net_income=net, periodicity=periodicity, currency=currency,
               period_start="2026-09-16", period_end="2026-09-30", issue_date="2026-09-30", **kw)
