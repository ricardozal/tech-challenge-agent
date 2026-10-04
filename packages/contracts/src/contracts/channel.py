"""Agent channel contract (contracts/agent-channel.md)."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from contracts.common import Stage, Status


class CreateCaseResponse(BaseModel):
    case_id: UUID
    reply: str
    stage: Stage
    status: Status


class MessageIn(BaseModel):
    text: str


class TurnCase(BaseModel):
    stage: Stage
    status: Status
    version: int


class ToolCallSummary(BaseModel):
    tool: str
    outcome: str
    rejection_code: str | None = None


class TurnResponse(BaseModel):
    message_id: str
    reply: str
    case: TurnCase
    tool_calls: list[ToolCallSummary] = []


class ConversationMessage(BaseModel):
    author: str
    text: str


class Conversation(BaseModel):
    case_id: UUID
    messages: list[ConversationMessage]
    state: dict[str, Any] = {}
