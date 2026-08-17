"""Optional Cua provider stub — always safe-unavailable without credentials."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.sandbox.provider import (
    CommandResult,
    FileEntry,
    ProviderCapabilities,
    ProviderError,
    SandboxInfo,
    SandboxStatus,
    ScreenshotResult,
    WORKSPACE_UNAVAILABLE,
)


class CuaSandboxProvider:
    name = "cua"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def is_available(self) -> bool:
        return bool(self.settings.cua_api_key)

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            shell=False,
            files=False,
            screenshot=False,
            gui_input=False,
            browser=False,
            notes="Cua requires early access / credentials; not configured.",
        )

    async def create(self, conversation_id: str) -> SandboxInfo:
        return SandboxInfo(
            conversation_id=conversation_id,
            status=SandboxStatus.unavailable,
            provider=self.name,
            message=f"{WORKSPACE_UNAVAILABLE}: Cua provider is not configured",
        )

    async def get(self, conversation_id: str, provider_ref: str | None) -> SandboxInfo:
        return await self.create(conversation_id)

    async def start(
        self, conversation_id: str, provider_ref: str | None
    ) -> SandboxInfo:
        return await self.create(conversation_id)

    async def stop(self, conversation_id: str, provider_ref: str | None) -> SandboxInfo:
        return SandboxInfo(
            conversation_id=conversation_id,
            status=SandboxStatus.stopped,
            provider=self.name,
            message="Cua not configured",
        )

    async def destroy(self, conversation_id: str, provider_ref: str | None) -> None:
        return None

    async def run_command(self, *args, **kwargs) -> CommandResult:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")

    async def read_file(self, *args, **kwargs) -> bytes:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")

    async def write_file(self, *args, **kwargs) -> None:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")

    async def list_dir(self, *args, **kwargs) -> list[FileEntry]:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")

    async def mkdir(self, *args, **kwargs) -> None:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")

    async def move_file(self, *args, **kwargs) -> None:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")

    async def delete_path(self, *args, **kwargs) -> None:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")

    async def screenshot(self, *args, **kwargs) -> ScreenshotResult:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")

    async def click(self, *args, **kwargs) -> None:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")

    async def scroll(self, *args, **kwargs) -> None:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")

    async def type_text(self, *args, **kwargs) -> None:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")

    async def keypress(self, *args, **kwargs) -> None:
        raise ProviderError(WORKSPACE_UNAVAILABLE, "Cua provider is not configured")
