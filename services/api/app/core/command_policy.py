"""Shared network and shell authorization for remote commands."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.approval_gate import consume_or_request_approval
from app.core.config import get_settings
from app.sandbox.paths import is_blocked_network_target
from app.sandbox.provider import ProviderError

_URL = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)
_SSH_HOST = re.compile(
    r"(?:^|\s)(?:git\+ssh://|ssh://|[\w.-]+@)([A-Za-z0-9.-]+)", re.IGNORECASE
)
_NETWORK_COMMAND = re.compile(
    r"(?:^|[;&|]\s*|\bsudo\s+)(?:curl|wget|ssh|scp|sftp|nc|ncat|telnet|ftp|git\s+(?:clone|fetch|pull|push)|pip\s+install|npm\s+(?:install|ci)|pnpm\s+install|yarn\s+install|apt(?:-get)?\s+(?:update|install)|dnf\s+install)\b",
    re.IGNORECASE,
)
_HOST_LITERAL = re.compile(
    r"(?<![A-Za-z0-9])(?:localhost|metadata\.google\.internal|(?:\d{1,3}\.){3}\d{1,3}|::1)(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def command_network_targets(command: str) -> set[str]:
    targets: set[str] = set()
    for raw in _URL.findall(command):
        try:
            host = urlsplit(raw.rstrip(".,);]")).hostname
        except ValueError:
            host = None
        if host:
            targets.add(host.lower())
    targets.update(match.lower() for match in _SSH_HOST.findall(command))
    targets.update(match.lower() for match in _HOST_LITERAL.findall(command))
    return targets


def command_uses_network(command: str) -> bool:
    return bool(command_network_targets(command) or _NETWORK_COMMAND.search(command))


async def authorize_remote_command(
    session: AsyncSession,
    *,
    conversation_id: str,
    command: str,
    cwd: str | None,
) -> dict[str, Any] | None:
    """Block internal targets and consume the required exact approvals."""
    settings = get_settings()
    targets = sorted(command_network_targets(command))
    blocked = [target for target in targets if is_blocked_network_target(target)]
    if settings.block_internal_network and blocked:
        raise ProviderError(
            "NETWORK_TARGET_BLOCKED",
            "Command references a blocked local, private, link-local, or metadata target",
            {"targets": blocked},
        )

    if settings.require_approval_for_network and command_uses_network(command):
        pending = await consume_or_request_approval(
            session,
            conversation_id=conversation_id,
            action="workspace.network",
            summary="Allow this remote command to use the network",
            details={"command": command, "cwd": cwd, "targets": targets},
        )
        if pending:
            return pending

    if settings.require_approval_for_shell:
        return await consume_or_request_approval(
            session,
            conversation_id=conversation_id,
            action="workspace.shell",
            summary=f"Run a remote shell command: {command[:240]}",
            details={"command": command, "cwd": cwd},
        )
    return None
