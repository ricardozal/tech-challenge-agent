"""Client of Document Intelligence; failures count as provider failures (FR-041)."""

import httpx

from actions_api.providers.base import ProviderError
from contracts.common import DocumentType
from contracts.documents import DocumentExtractRequest, DocumentExtractResponse


class DocumentReader:
    def __init__(self, base_url: str, http: httpx.Client | None = None):
        self._http = http or httpx.Client(base_url=base_url, timeout=330)

    def extract(self, expected_type: DocumentType, mime_type: str, content_base64: str) -> DocumentExtractResponse:
        body = DocumentExtractRequest(expected_type=expected_type, mime_type=mime_type, content_base64=content_base64)
        try:
            resp = self._http.post("/v1/documents/extract", json=body.model_dump(mode="json"))
        except httpx.HTTPError as exc:
            raise ProviderError(f"doc_intel: {exc}") from exc
        if resp.status_code != 200:
            raise ProviderError(f"doc_intel: HTTP {resp.status_code}")
        return DocumentExtractResponse.model_validate(resp.json())
