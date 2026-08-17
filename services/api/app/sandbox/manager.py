"""Conversation-scoped workspace lifecycle manager."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.entities import WorkspaceRecord, WorkspaceStatus
from app.sandbox.cua_provider import CuaSandboxProvider
from app.sandbox.e2b_provider import E2BSandboxProvider
from app.sandbox.local_provider import LocalSandboxProvider
from app.sandbox.provider import (
    ProviderError,
    SandboxInfo,
    SandboxProvider,
    SandboxStatus,
    ScreenshotResult,
    WORKSPACE_UNAVAILABLE,
)

log = get_logger(__name__)

_manager: WorkspaceManager | None = None


def build_provider(settings: Settings | None = None) -> SandboxProvider:
    settings = settings or get_settings()
    name = settings.sandbox_provider
    if name == "e2b":
        return E2BSandboxProvider(settings)
    if name == "cua":
        return CuaSandboxProvider(settings)
    return LocalSandboxProvider(settings)


class WorkspaceManager:
    """
    Owns conversation → sandbox mapping.
    Model/tools never pass arbitrary sandbox IDs; they pass conversation_id only.
    """

    def __init__(
        self,
        provider: SandboxProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider: SandboxProvider = provider or build_provider(self.settings)
        self._locks: dict[str, asyncio.Lock] = {}
        self._global = asyncio.Lock()

    def _lock_for(self, conversation_id: str) -> asyncio.Lock:
        if conversation_id not in self._locks:
            self._locks[conversation_id] = asyncio.Lock()
        return self._locks[conversation_id]

    async def _get_or_create_record(
        self, session: AsyncSession, conversation_id: str
    ) -> WorkspaceRecord:
        result = await session.execute(
            select(WorkspaceRecord).where(
                WorkspaceRecord.conversation_id == conversation_id
            )
        )
        rec = result.scalar_one_or_none()
        if rec is None:
            rec = WorkspaceRecord(
                conversation_id=conversation_id,
                provider=self.provider.name,
                status=WorkspaceStatus.none,
                idle_timeout_sec=self.settings.sandbox_idle_timeout_sec,
            )
            session.add(rec)
            await session.commit()
            await session.refresh(rec)
        return rec

    @staticmethod
    def _map_status(info: SandboxInfo) -> WorkspaceStatus:
        try:
            return WorkspaceStatus(info.status.value)
        except ValueError:
            return WorkspaceStatus.error

    async def status(
        self, session: AsyncSession, conversation_id: str
    ) -> dict[str, Any]:
        rec = await self._get_or_create_record(session, conversation_id)
        try:
            info = await self.provider.get(conversation_id, rec.provider_ref)
        except Exception as exc:
            log.exception("provider get failed")
            info = SandboxInfo(
                conversation_id=conversation_id,
                status=SandboxStatus.error,
                provider=self.provider.name,
                message=str(exc),
            )
        # keep DB roughly in sync when provider knows more
        if info.status != SandboxStatus.none:
            rec.status = self._map_status(info)
            if info.sandbox_id:
                rec.provider_ref = info.sandbox_id
            if info.message and info.status in {
                SandboxStatus.error,
                SandboxStatus.unavailable,
            }:
                rec.last_error = info.message
            await session.commit()
        public = info.to_public_dict()
        public["db_status"] = rec.status.value
        public["last_error"] = rec.last_error
        public["last_active_at"] = (
            rec.last_active_at.isoformat() if rec.last_active_at else None
        )
        caps = await self.provider.capabilities()
        public["capabilities"] = {
            "shell": caps.shell,
            "files": caps.files,
            "screenshot": caps.screenshot,
            "gui_input": caps.gui_input,
            "browser": caps.browser,
            "notes": caps.notes,
        }
        return public

    async def start(
        self, session: AsyncSession, conversation_id: str
    ) -> dict[str, Any]:
        async with self._lock_for(conversation_id):
            rec = await self._get_or_create_record(session, conversation_id)

            # Concurrency cap — never count this conversation against itself
            if rec.status != WorkspaceStatus.running:
                running = await session.execute(
                    select(WorkspaceRecord).where(
                        WorkspaceRecord.status == WorkspaceStatus.running,
                        WorkspaceRecord.conversation_id != conversation_id,
                    )
                )
                if len(list(running.scalars())) >= self.settings.sandbox_max_concurrent:
                    raise ProviderError(
                        "CONCURRENCY_LIMIT",
                        f"Max concurrent workspaces ({self.settings.sandbox_max_concurrent}) reached",
                    )
            rec.status = WorkspaceStatus.starting
            rec.provider = self.provider.name
            rec.last_error = None
            await session.commit()

            try:
                if rec.provider_ref:
                    info = await self.provider.start(conversation_id, rec.provider_ref)
                else:
                    info = await self.provider.create(conversation_id)
            except Exception:
                log.exception("workspace start failed")
                rec.status = WorkspaceStatus.error
                rec.last_error = "Workspace provider failed; check server logs"
                await session.commit()
                return {
                    "conversation_id": conversation_id,
                    "status": WorkspaceStatus.error.value,
                    "provider": self.provider.name,
                    "message": f"{WORKSPACE_UNAVAILABLE}: provider start failed",
                }

            rec.status = self._map_status(info)
            rec.provider_ref = info.sandbox_id or rec.provider_ref
            rec.last_active_at = datetime.now(timezone.utc)
            if info.status in {SandboxStatus.unavailable, SandboxStatus.error}:
                rec.last_error = info.message
            await session.commit()
            return info.to_public_dict()

    async def stop(self, session: AsyncSession, conversation_id: str) -> dict[str, Any]:
        async with self._lock_for(conversation_id):
            rec = await self._get_or_create_record(session, conversation_id)
            rec.status = WorkspaceStatus.stopping
            await session.commit()
            try:
                info = await self.provider.stop(conversation_id, rec.provider_ref)
            except Exception:
                log.exception("workspace stop failed")
                rec.status = WorkspaceStatus.error
                rec.last_error = "Workspace provider failed; check server logs"
                await session.commit()
                raise
            rec.status = WorkspaceStatus.stopped
            await session.commit()
            return info.to_public_dict()

    async def restart(
        self, session: AsyncSession, conversation_id: str
    ) -> dict[str, Any]:
        """Pause and reconnect the same provider workspace."""
        await self.stop(session, conversation_id)
        return await self.start(session, conversation_id)

    async def destroy(self, session: AsyncSession, conversation_id: str) -> None:
        """Permanently delete provider state and clear the persisted handle."""
        async with self._lock_for(conversation_id):
            rec = await self._get_or_create_record(session, conversation_id)
            await self.provider.destroy(conversation_id, rec.provider_ref)
            rec.provider_ref = None
            rec.status = WorkspaceStatus.none
            rec.last_error = None
            rec.last_active_at = None
            await session.commit()

    async def ensure_running(
        self, session: AsyncSession, conversation_id: str
    ) -> WorkspaceRecord:
        rec = await self._get_or_create_record(session, conversation_id)
        if rec.status == WorkspaceStatus.running and rec.provider_ref:
            info = await self.provider.get(conversation_id, rec.provider_ref)
            if info.status == SandboxStatus.running:
                rec.last_active_at = datetime.now(timezone.utc)
                await session.commit()
                return rec
        await self.start(session, conversation_id)
        await session.refresh(rec)
        if rec.status not in {WorkspaceStatus.running, WorkspaceStatus.starting}:
            # re-read
            await session.refresh(rec)
        if rec.status != WorkspaceStatus.running:
            raise ProviderError(
                WORKSPACE_UNAVAILABLE,
                rec.last_error or "Workspace failed to start",
            )
        return rec

    async def execute(
        self,
        session: AsyncSession,
        conversation_id: str,
        command: str,
        *,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> dict[str, Any]:
        rec = await self.ensure_running(session, conversation_id)
        result = await self.provider.run_command(
            conversation_id,
            rec.provider_ref,
            command,
            cwd=cwd,
            timeout_sec=timeout_sec or self.settings.sandbox_max_command_timeout_sec,
        )
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()
        return result.to_public_dict()

    async def read_file(
        self, session: AsyncSession, conversation_id: str, path: str
    ) -> bytes:
        rec = await self.ensure_running(session, conversation_id)
        data = await self.provider.read_file(conversation_id, rec.provider_ref, path)
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()
        return data

    async def write_file(
        self,
        session: AsyncSession,
        conversation_id: str,
        path: str,
        data: bytes,
    ) -> None:
        rec = await self.ensure_running(session, conversation_id)
        await self.provider.write_file(conversation_id, rec.provider_ref, path, data)
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()

    async def list_dir(
        self, session: AsyncSession, conversation_id: str, path: str
    ) -> list[dict[str, Any]]:
        rec = await self.ensure_running(session, conversation_id)
        entries = await self.provider.list_dir(conversation_id, rec.provider_ref, path)
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()
        return [e.to_public_dict() for e in entries]

    async def mkdir(
        self, session: AsyncSession, conversation_id: str, path: str
    ) -> None:
        rec = await self.ensure_running(session, conversation_id)
        await self.provider.mkdir(conversation_id, rec.provider_ref, path)
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()

    async def move_file(
        self,
        session: AsyncSession,
        conversation_id: str,
        src: str,
        dst: str,
    ) -> None:
        rec = await self.ensure_running(session, conversation_id)
        await self.provider.move_file(conversation_id, rec.provider_ref, src, dst)
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()

    async def delete_path(
        self, session: AsyncSession, conversation_id: str, path: str
    ) -> None:
        rec = await self.ensure_running(session, conversation_id)
        await self.provider.delete_path(conversation_id, rec.provider_ref, path)
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()

    async def screenshot(
        self, session: AsyncSession, conversation_id: str
    ) -> ScreenshotResult:
        rec = await self.ensure_running(session, conversation_id)
        shot = await self.provider.screenshot(conversation_id, rec.provider_ref)
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()
        return shot

    async def click(
        self,
        session: AsyncSession,
        conversation_id: str,
        x: int,
        y: int,
        *,
        double: bool = False,
    ) -> None:
        rec = await self.ensure_running(session, conversation_id)
        await self.provider.click(
            conversation_id, rec.provider_ref, x, y, double=double
        )
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()

    async def scroll(
        self, session: AsyncSession, conversation_id: str, amount: int
    ) -> None:
        rec = await self.ensure_running(session, conversation_id)
        await self.provider.scroll(conversation_id, rec.provider_ref, amount)
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()

    async def type_text(
        self, session: AsyncSession, conversation_id: str, text: str
    ) -> None:
        rec = await self.ensure_running(session, conversation_id)
        await self.provider.type_text(conversation_id, rec.provider_ref, text)
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()

    async def keypress(
        self,
        session: AsyncSession,
        conversation_id: str,
        keys: str | list[str],
    ) -> None:
        rec = await self.ensure_running(session, conversation_id)
        await self.provider.keypress(conversation_id, rec.provider_ref, keys)
        rec.last_active_at = datetime.now(timezone.utc)
        await session.commit()

    async def idle_reap(self, session: AsyncSession) -> int:
        """Stop workspaces idle beyond timeout. Returns count stopped."""
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(WorkspaceRecord).where(
                WorkspaceRecord.status == WorkspaceStatus.running
            )
        )
        stopped = 0
        for rec in result.scalars():
            if not rec.last_active_at:
                continue
            idle = (now - rec.last_active_at).total_seconds()
            if idle >= (rec.idle_timeout_sec or self.settings.sandbox_idle_timeout_sec):
                try:
                    await self.stop(session, rec.conversation_id)
                    stopped += 1
                except Exception:
                    log.exception("idle stop failed for %s", rec.conversation_id)
        return stopped


def get_workspace_manager() -> WorkspaceManager:
    global _manager
    if _manager is None:
        _manager = WorkspaceManager()
    return _manager


def reset_workspace_manager(
    manager: WorkspaceManager | None = None,
) -> WorkspaceManager:
    """Test helper."""
    global _manager
    _manager = manager if manager is not None else WorkspaceManager()
    return _manager
