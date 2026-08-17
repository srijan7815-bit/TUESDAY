"""Streaming chat endpoint with optional agent tool loop."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agent.loop import AgentLoop
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_session
from app.memory.store import MemoryStore
from app.models.entities import Conversation, Message
from app.sandbox.manager import get_workspace_manager

log = get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["chat"])


class ChatMessageIn(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1, max_length=64_000)


class ChatStreamRequest(BaseModel):
    messages: list[ChatMessageIn] = Field(default_factory=list, max_length=100)
    conversation_id: str | None = Field(
        default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$"
    )
    model: str | None = None
    temperature: float = Field(default=0.5, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=16_384)
    enable_tools: bool = True
    task: str = "chat"


async def _ensure_conversation(
    session: AsyncSession, conversation_id: str | None
) -> Conversation:
    if conversation_id:
        row = await session.get(Conversation, conversation_id)
        if row:
            return row
    row = Conversation(id=conversation_id or str(uuid.uuid4()))
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.post("/chat/stream")
async def chat_stream(
    body: ChatStreamRequest,
) -> EventSourceResponse:
    """SSE chat — owns its DB session for the full stream lifetime."""
    from app.db.session import async_session_factory, init_db

    if async_session_factory is None:
        await init_db()
    assert async_session_factory is not None

    async with async_session_factory() as session:
        conv = await _ensure_conversation(session, body.conversation_id)
        conversation_id = conv.id

        stored_result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(60)
        )
        stored_rows = list(reversed(stored_result.scalars().all()))

        user_msgs = [m for m in body.messages if m.role == "user"]
        if user_msgs:
            session.add(
                Message(
                    conversation_id=conversation_id,
                    role="user",
                    content=user_msgs[-1].content,
                )
            )
            await session.commit()

        memory = MemoryStore()
        mem_block = await memory.prompt_block(session) if conv.memory_enabled else ""

    messages: list[dict[str, Any]] = []
    if mem_block:
        messages.append({"role": "system", "content": mem_block})
    # Thin clients send only the newest message. Full clients can send an
    # explicit transcript and remain authoritative for that request.
    if len(body.messages) <= 1:
        for row in stored_rows:
            messages.append({"role": row.role, "content": row.content})
    for incoming in body.messages:
        messages.append({"role": incoming.role, "content": incoming.content})

    loop = AgentLoop(manager=get_workspace_manager())
    settings = get_settings()

    async def event_gen():
        yield {
            "event": "session",
            "data": json.dumps(
                {
                    "conversation_id": conversation_id,
                    "mock_model": not settings.has_nvidia,
                    "sandbox_provider": settings.sandbox_provider,
                }
            ),
        }
        final_text = ""
        final_model = None
        try:
            async with async_session_factory() as stream_session:
                async for evt in loop.run_stream(
                    stream_session,
                    conversation_id=conversation_id,
                    messages=messages,
                    model=body.model,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                    enable_tools=body.enable_tools,
                    task=body.task,
                ):
                    if evt["event"] == "done":
                        data = evt.get("data") or {}
                        # Prefer done payload content if non-empty; else keep deltas
                        if data.get("content"):
                            final_text = data["content"]
                        final_model = data.get("model") or final_model
                    elif evt["event"] == "delta":
                        final_text += (evt.get("data") or {}).get("content") or ""
                    yield {
                        "event": evt["event"],
                        "data": json.dumps(evt.get("data") or {}, ensure_ascii=False),
                    }

                if final_text:
                    stream_session.add(
                        Message(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=final_text,
                            model=final_model,
                        )
                    )
                    await stream_session.commit()
        except Exception:
            log.exception("chat stream failed")
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": "Chat request failed; check server logs"}
                ),
            }
            return

    return EventSourceResponse(event_gen())


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    rows = result.scalars().all()
    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "model": m.model,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ],
    }
