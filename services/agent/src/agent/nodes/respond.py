"""respond: Spanish reply from structured facts (LLM), never from raw document text (R-19)."""

from typing import Any

from agent import questions
from agent.graph import Deps, TurnState
from contracts.common import Status
from contracts.llm import ReplyRequest

GREETING = (
    "Hola, soy el asistente virtual. Te ayudo a solicitar un crédito personal con tu auto como garantía; "
    "tú sigues usando tu auto."
)


async def respond(state: TurnState, deps: Deps) -> dict[str, Any]:
    view = await deps.get_case(state)
    next_question = state.get("next_question")
    if view.status != Status.active:
        next_question = None
    elif next_question is None:
        question = questions.next_question(view)
        next_question = question.text if question else None

    facts = dict(state.get("facts") or {})
    if state.get("kind") == "start":
        facts.setdefault("note_es", GREETING)
    full_name = view.state.client.full_name
    reply = await deps.llm.reply(
        ReplyRequest(
            stage=view.stage,
            status=view.status,
            facts=facts,
            next_question=next_question,
            client_first_name=full_name.split()[0] if full_name else None,
        )
    )

    current = {"id": str(view.id), "stage": view.stage.value, "status": view.status.value, "version": view.version}
    _, updates = await deps.call_tool(
        {**state, "case": current},
        "append_message",
        {"message_id": f"{state['message_id']}:agent", "author": "agent", "text": reply.text},
    )

    history = list(state.get("history") or [])
    if state.get("kind") == "message":
        history.append({"author": "client", "text": state.get("text") or ""})
    elif state.get("kind") == "document":
        document = state.get("document") or {}
        history.append({"author": "client", "text": f"[documento: {document.get('requested_type')}]"})
    history.append({"author": "agent", "text": reply.text})
    return {**updates, "reply": reply.text, "next_question": next_question, "last_question": next_question, "history": history}
