"""Provider protocol and stable public DTOs — never leak raw SDK objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


WORKSPACE_UNAVAILABLE = "WORKSPACE_UNAVAILABLE"


class SandboxStatus(str, Enum):
    none = "none"
    starting = "starting"
    running = "running"
    stopping = "stopping"
    stopped = "stopped"
    error = "error"
    unavailable = "unavailable"


@dataclass(slots=True)
class SandboxInfo:
    conversation_id: str
    status: SandboxStatus
    provider: str
    sandbox_id: str | None = None
    message: str | None = None
    screen: dict[str, int] | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "status": self.status.value,
            "provider": self.provider,
            "sandbox_id": self.sandbox_id,
            "message": self.message,
            "screen": self.screen,
        }


@dataclass(slots=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    truncated: bool = False

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "truncated": self.truncated,
        }


@dataclass(slots=True)
class FileEntry:
    path: str
    name: str
    is_dir: bool
    size: int = 0

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "is_dir": self.is_dir,
            "size": self.size,
        }


@dataclass(slots=True)
class ScreenshotResult:
    content_type: str
    data: bytes
    width: int | None = None
    height: int | None = None


@dataclass(slots=True)
class ProviderCapabilities:
    shell: bool = True
    files: bool = True
    screenshot: bool = False
    gui_input: bool = False
    browser: bool = False
    notes: str = ""


@runtime_checkable
class SandboxProvider(Protocol):
    name: str

    async def is_available(self) -> bool: ...

    async def create(self, conversation_id: str) -> SandboxInfo: ...

    async def get(
        self, conversation_id: str, provider_ref: str | None
    ) -> SandboxInfo: ...

    async def start(
        self, conversation_id: str, provider_ref: str | None
    ) -> SandboxInfo: ...

    async def stop(
        self, conversation_id: str, provider_ref: str | None
    ) -> SandboxInfo: ...

    async def destroy(self, conversation_id: str, provider_ref: str | None) -> None: ...

    async def run_command(
        self,
        conversation_id: str,
        provider_ref: str | None,
        command: str,
        *,
        cwd: str | None = None,
        timeout_sec: int = 60,
        env: dict[str, str] | None = None,
    ) -> CommandResult: ...

    async def read_file(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
        *,
        max_bytes: int = 1_048_576,
    ) -> bytes: ...

    async def write_file(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
        data: bytes,
    ) -> None: ...

    async def list_dir(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
    ) -> list[FileEntry]: ...

    async def mkdir(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
    ) -> None: ...

    async def move_file(
        self,
        conversation_id: str,
        provider_ref: str | None,
        src: str,
        dst: str,
    ) -> None: ...

    async def delete_path(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
    ) -> None: ...

    async def screenshot(
        self,
        conversation_id: str,
        provider_ref: str | None,
    ) -> ScreenshotResult: ...

    async def click(
        self,
        conversation_id: str,
        provider_ref: str | None,
        x: int,
        y: int,
        *,
        double: bool = False,
    ) -> None: ...

    async def scroll(
        self,
        conversation_id: str,
        provider_ref: str | None,
        amount: int,
    ) -> None: ...

    async def type_text(
        self,
        conversation_id: str,
        provider_ref: str | None,
        text: str,
    ) -> None: ...

    async def keypress(
        self,
        conversation_id: str,
        provider_ref: str | None,
        keys: str | list[str],
    ) -> None: ...

    async def capabilities(self) -> ProviderCapabilities: ...


@dataclass
class ProviderError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
