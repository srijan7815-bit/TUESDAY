"""Approval gate for consequential actions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import Approval, ApprovalStatus

router = APIRouter(prefix="/v1/approvals", tags=["approvals"])


class CreateApprovalBody(BaseModel):
    conversation_id: str
    action: str = Field(..., max_length=64)
    summary: str = Field(..., max_length=2000)
    details: dict[str, Any] = Field(default_factory=dict)


class ResolveBody(BaseModel):
    decision: str = Field(..., pattern="^(approved|denied)$")


@router.post("")
async def create_approval(
    body: CreateApprovalBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = Approval(
        conversation_id=body.conversation_id,
        action=body.action,
        summary=body.summary,
        details_json=json.dumps(body.details),
        status=ApprovalStatus.pending,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _public(row)


@router.get("/pending")
async def list_pending(
    conversation_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    q = select(Approval).where(Approval.status == ApprovalStatus.pending)
    if conversation_id:
        q = q.where(Approval.conversation_id == conversation_id)
    rows = (
        (await session.execute(q.order_by(Approval.created_at.desc()))).scalars().all()
    )
    return {"approvals": [_public(r) for r in rows]}


@router.post("/{approval_id}")
async def resolve_approval(
    approval_id: str,
    body: ResolveBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await session.get(Approval, approval_id)
    if not row:
        raise HTTPException(status_code=404, detail="Approval not found")
    if row.status != ApprovalStatus.pending:
        raise HTTPException(status_code=400, detail="Approval already resolved")
    row.status = (
        ApprovalStatus.approved
        if body.decision == "approved"
        else ApprovalStatus.denied
    )
    row.resolved_at = datetime.now(timezone.utc)
    await session.commit()
    return _public(row)


def _public(row: Approval) -> dict[str, Any]:
    try:
        details = json.loads(row.details_json or "{}")
    except json.JSONDecodeError:
        details = {}
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "action": row.action,
        "summary": row.summary,
        "details": details,
        "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "used_at": row.used_at.isoformat() if row.used_at else None,
    }
