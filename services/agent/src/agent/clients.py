"""HTTP clients for the Case Actions API and the LLM Gateway. Only `contracts` models cross the wire."""

from uuid import UUID

import httpx

from contracts.actions import ToolCall, ToolContext, ToolResult
from contracts.case import CaseView
from contracts.llm import ExtractRequest, ExtractResponse, ReplyRequest, ReplyResponse

# Drop idle connections before uvicorn does (its keep-alive timeout is 5 s): with real models a call
# can follow the previous one after more than 5 s, and reusing a connection the server is closing
# fails with ReadError.
LIMITS = httpx.Limits(keepalive_expiry=2.0)


class UpstreamError(RuntimeError):
    pass


async def _send(service: str, request) -> httpx.Response:
    """A service that does not answer (connection error or timeout) is an UpstreamError: the channel
    answers 502 upstream_failure and the turn span is marked ERROR, never a 500 with a traceback."""
    try:
        return await request
    except httpx.HTTPError as exc:
        raise UpstreamError(f"{service}: {type(exc).__name__}: {exc}") from exc


class ActionsClient:
    def __init__(self, base_url: str, http: httpx.AsyncClient | None = None):
        self._http = http or httpx.AsyncClient(base_url=base_url, timeout=330, limits=LIMITS)

    async def call(self, tool: str, context: ToolContext, tool_input: dict | None = None) -> ToolResult:
        call = ToolCall(context=context, input=tool_input or {})
        resp = await _send(f"actions_api {tool}", self._http.post(
            f"/tools/{tool}", json=call.model_dump(mode="json"), headers={"X-Actor": "agent"}
        ))
        try:
            body = resp.json()
        except ValueError:
            raise UpstreamError(f"actions_api {tool}: HTTP {resp.status_code}") from None
        if "outcome" not in body:
            raise UpstreamError(f"actions_api {tool}: HTTP {resp.status_code} {body}")
        return ToolResult.model_validate(body)

    async def get_case(self, case_id: UUID | str) -> CaseView:
        resp = await _send("actions_api get_case", self._http.get(f"/cases/{case_id}"))
        if resp.status_code != 200:
            raise UpstreamError(f"actions_api get_case: HTTP {resp.status_code}")
        return CaseView.model_validate(resp.json())

    async def aclose(self) -> None:
        await self._http.aclose()


class LlmClient:
    def __init__(self, base_url: str, http: httpx.AsyncClient | None = None):
        self._http = http or httpx.AsyncClient(base_url=base_url, timeout=330, limits=LIMITS)

    async def extract(self, req: ExtractRequest) -> ExtractResponse:
        resp = await _send("llm_gateway extract", self._http.post("/v1/extract", json=req.model_dump(mode="json")))
        if resp.status_code != 200:
            raise UpstreamError(f"llm_gateway extract: HTTP {resp.status_code} {resp.text[:200]}")
        return ExtractResponse.model_validate(resp.json())

    async def reply(self, req: ReplyRequest) -> ReplyResponse:
        resp = await _send("llm_gateway reply", self._http.post("/v1/reply", json=req.model_dump(mode="json")))
        if resp.status_code != 200:
            raise UpstreamError(f"llm_gateway reply: HTTP {resp.status_code} {resp.text[:200]}")
        return ReplyResponse.model_validate(resp.json())

    async def aclose(self) -> None:
        await self._http.aclose()
