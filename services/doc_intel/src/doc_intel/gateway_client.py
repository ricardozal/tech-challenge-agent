"""Calls to the LLM Gateway (OCR and extraction). doc_intel never talks to Ollama directly."""

import httpx

from contracts.llm import ExtractRequest, ExtractResponse, OcrRequest, OcrResponse

# Drop idle connections before uvicorn does (its keep-alive timeout is 5 s): with real models a call
# can follow the previous one after more than 5 s, and reusing a connection the server is closing
# fails with ReadError.
LIMITS = httpx.Limits(keepalive_expiry=2.0)


class UpstreamFailure(RuntimeError):
    pass


class GatewayClient:
    def __init__(self, base_url: str, http: httpx.Client | None = None):
        self._http = http or httpx.Client(base_url=base_url, timeout=330, limits=LIMITS)

    def _post(self, path: str, body: dict) -> dict:
        try:
            resp = self._http.post(path, json=body)
        except httpx.HTTPError as exc:
            raise UpstreamFailure(f"llm_gateway {path}: {exc}") from exc
        if resp.status_code != 200:
            raise UpstreamFailure(f"llm_gateway {path}: HTTP {resp.status_code} {resp.text[:200]}")
        return resp.json()

    def ocr(self, req: OcrRequest) -> OcrResponse:
        return OcrResponse.model_validate(self._post("/v1/ocr", req.model_dump(mode="json")))

    def extract(self, req: ExtractRequest) -> ExtractResponse:
        return ExtractResponse.model_validate(self._post("/v1/extract", req.model_dump(mode="json")))
