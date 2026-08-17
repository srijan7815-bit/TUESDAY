"""Memory inspect / save / forget / export / disable APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.memory.store import MemoryStore

router = APIRouter(prefix="/v1/memory", tags=["memory"])
store = MemoryStore()


class RememberBody(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    kind: str = "preference"
    key: str | None = None
    conversation_id: str | None = None


class EnableBody(BaseModel):
    enabled: bool


@router.get("")
async def list_memory(
    kind: str | None = None,
    include_disabled: bool = False,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    entries = await store.list_entries(
        session, kind=kind, include_disabled=include_disabled
    )
    return {"entries": entries, "count": len(entries)}


@router.post("/remember")
async def remember(
    body: RememberBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await store.remember(
        session,
        content=body.content,
        kind=body.kind,
        key=body.key,
        conversation_id=body.conversation_id,
    )


@router.delete("/{entry_id}")
async def forget(
    entry_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await store.forget(session, entry_id)


@router.post("/{entry_id}/enabled")
async def set_enabled(
    entry_id: str,
    body: EnableBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await store.set_enabled(session, entry_id, body.enabled)


@router.get("/export")
async def export_memory(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await store.export_all(session)


@router.delete("")
async def delete_all_memory(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await store.delete_all(session)
