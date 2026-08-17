"""Reusable approval checks for consequential workspace operations."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Approval, ApprovalStatus


def action_fingerprint(action: str, details: dict[str, Any]) -> str:
    canonical = json.dumps(
        details, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(f"{action}:{canonical}".encode("utf-8")).hexdigest()


async def consume_or_request_approval(
    session: AsyncSession,
    *,
    conversation_id: str,
    action: str,
    summary: str,
    details: dict[str, Any],
) -> dict[str, Any] | None:
    """Return pending metadata or consume one matching approval and return None."""
    fingerprint = action_fingerprint(action, details)
    rows = (
        (
            await session.execute(
                select(Approval)
                .where(
                    Approval.conversation_id == conversation_id,
                    Approval.action == action,
                    Approval.status.in_(
                        [ApprovalStatus.pending, ApprovalStatus.approved]
                    ),
                )
                .order_by(Approval.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        try:
            stored = json.loads(row.details_json or "{}")
        except json.JSONDecodeError:
            continue
        if stored.get("fingerprint") != fingerprint:
            continue
        if row.status == ApprovalStatus.approved and row.used_at is None:
            row.used_at = datetime.now(timezone.utc)
            await session.commit()
            return None
        if row.status == ApprovalStatus.pending:
            return {
                "ok": False,
                "approval_required": True,
                "approval_id": row.id,
                "action": action,
                "summary": row.summary,
            }

    stored_details = {**details, "fingerprint": fingerprint}
    row = Approval(
        conversation_id=conversation_id,
        action=action,
        summary=summary,
        details_json=json.dumps(stored_details, ensure_ascii=False),
        status=ApprovalStatus.pending,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {
        "ok": False,
        "approval_required": True,
        "approval_id": row.id,
        "action": action,
        "summary": summary,
    }
