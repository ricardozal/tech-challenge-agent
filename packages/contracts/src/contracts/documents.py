"""Document Intelligence contract (contracts/doc-intel.md)."""

from pydantic import BaseModel, Field

from contracts.common import DocumentType


class DocumentExtractRequest(BaseModel):
    expected_type: DocumentType
    mime_type: str = "image/png"
    content_base64: str


class ExtractedField(BaseModel):
    value: str | int | float | bool | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class DocumentExtractResponse(BaseModel):
    detected_type: DocumentType
    type_matches: bool
    is_test_specimen: bool
    # Keys of the `documento` schema in eval/esquemas.json (Spanish, R-01).
    fields: dict[str, ExtractedField]
    ocr_chars: int
