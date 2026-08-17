"""Explicit memory with inspect / save / forget / export / disable."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import MemoryEntry, MemoryKind


class MemoryStore:
    async def list_entries(
        self,
        session: AsyncSession,
        *,
        kind: str | None = None,
        include_disabled: bool = False,
        conversation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        q = select(MemoryEntry).order_by(MemoryEntry.updated_at.desc())
        if kind:
            q = q.where(MemoryEntry.kind == MemoryKind(kind))
        if not include_disabled:
            q = q.where(MemoryEntry.enabled.is_(True))
        if conversation_id:
            q = q.where(
                (MemoryEntry.conversation_id == conversation_id)
                | (MemoryEntry.conversation_id.is_(None))
            )
        rows = (await session.execute(q)).scalars().all()
        return [self._public(r) for r in rows]

    async def remember(
        self,
        session: AsyncSession,
        *,
        content: str,
        kind: str = "preference",
        key: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        if not get_settings().memory_enabled:
            return {"ok": False, "error": "Memory is disabled globally"}
        entry = MemoryEntry(
            kind=MemoryKind(kind),
            key=key,
            content=content,
            conversation_id=conversation_id,
            enabled=True,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return {"ok": True, "entry": self._public(entry)}

    async def forget(self, session: AsyncSession, entry_id: str) -> dict[str, Any]:
        row = await session.get(MemoryEntry, entry_id)
        if not row:
            return {"ok": False, "error": "Not found"}
        await session.delete(row)
        await session.commit()
        return {"ok": True, "deleted": entry_id}

    async def set_enabled(
        self, session: AsyncSession, entry_id: str, enabled: bool
    ) -> dict[str, Any]:
        row = await session.get(MemoryEntry, entry_id)
        if not row:
            return {"ok": False, "error": "Not found"}
        row.enabled = enabled
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return {"ok": True, "entry": self._public(row)}

    async def delete_all(self, session: AsyncSession) -> dict[str, Any]:
        rows = (await session.execute(select(MemoryEntry))).scalars().all()
        n = 0
        for r in rows:
            await session.delete(r)
            n += 1
        await session.commit()
        return {"ok": True, "deleted": n}

    async def export_all(self, session: AsyncSession) -> dict[str, Any]:
        entries = await self.list_entries(session, include_disabled=True)
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "count": len(entries),
            "entries": entries,
        }

    async def prompt_block(self, session: AsyncSession) -> str:
        """Build a memory block for the model — only enabled entries."""
        if not get_settings().memory_enabled:
            return ""
        entries = await self.list_entries(session, include_disabled=False)
        if not entries:
            return ""
        lines = ["## User memory (enabled only)"]
        for e in entries[:50]:
            prefix = f"[{e['kind']}]"
            if e.get("key"):
                prefix += f" {e['key']}:"
            lines.append(f"- {prefix} {e['content']}")
        return "\n".join(lines)

    @staticmethod
    def _public(row: MemoryEntry) -> dict[str, Any]:
        return {
            "id": row.id,
            "kind": row.kind.value if hasattr(row.kind, "value") else str(row.kind),
            "key": row.key,
            "content": row.content,
            "enabled": row.enabled,
            "conversation_id": row.conversation_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
