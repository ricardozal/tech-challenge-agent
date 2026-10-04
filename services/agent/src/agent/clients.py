"""HTTP clients for the Case Actions API and the LLM Gateway. Only `contracts` models cross the wire."""

from uuid import UUID

import httpx

from contracts.actions import ToolCall, ToolContext, ToolResult
from contracts.case import CaseView
from contracts.llm import ExtractRequest, ExtractResponse, ReplyRequest, ReplyResponse


class UpstreamError(RuntimeError):
    pass


class ActionsClient:
    def __init__(self, base_url: str, http: httpx.AsyncClient | None = None):
        self._http = http or httpx.AsyncClient(base_url=base_url, timeout=330)

    async def call(self, tool: str, context: ToolContext, tool_input: dict | None = None) -> ToolResult:
        call = ToolCall(context=context, input=tool_input or {})
        resp = await self._http.post(
            f"/tools/{tool}", json=call.model_dump(mode="json"), headers={"X-Actor": "agent"}
        )
        try:
            body = resp.json()
        except ValueError:
            raise UpstreamError(f"actions_api {tool}: HTTP {resp.status_code}") from None
        if "outcome" not in body:
            raise UpstreamError(f"actions_api {tool}: HTTP {resp.status_code} {body}")
        return ToolResult.model_validate(body)

    async def get_case(self, case_id: UUID | str) -> CaseView:
        resp = await self._http.get(f"/cases/{case_id}")
        if resp.status_code != 200:
            raise UpstreamError(f"actions_api get_case: HTTP {resp.status_code}")
        return CaseView.model_validate(resp.json())

    async def aclose(self) -> None:
        await self._http.aclose()


class LlmClient:
    def __init__(self, base_url: str, http: httpx.AsyncClient | None = None):
        self._http = http or httpx.AsyncClient(base_url=base_url, timeout=330)

    async def extract(self, req: ExtractRequest) -> ExtractResponse:
        resp = await self._http.post("/v1/extract", json=req.model_dump(mode="json"))
        if resp.status_code != 200:
            raise UpstreamError(f"llm_gateway extract: HTTP {resp.status_code} {resp.text[:200]}")
        return ExtractResponse.model_validate(resp.json())

    async def reply(self, req: ReplyRequest) -> ReplyResponse:
        resp = await self._http.post("/v1/reply", json=req.model_dump(mode="json"))
        if resp.status_code != 200:
            raise UpstreamError(f"llm_gateway reply: HTTP {resp.status_code} {resp.text[:200]}")
        return ReplyResponse.model_validate(resp.json())

    async def aclose(self) -> None:
        await self._http.aclose()
