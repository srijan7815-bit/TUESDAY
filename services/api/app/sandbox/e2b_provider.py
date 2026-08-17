"""E2B cloud sandbox adapter — optional; safe unavailable path."""

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.sandbox.paths import LOGICAL_ROOT, normalize_workspace_path
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

log = get_logger(__name__)


class E2BSandboxProvider:
    """
    Adapter over the E2B SDK.

    We import e2b lazily and never expose raw SDK objects through the API.
    If the SDK or API key is missing, operations return WORKSPACE_UNAVAILABLE.
    """

    name = "e2b"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._sandboxes: dict[str, Any] = {}  # conversation_id -> sandbox instance
        self._sdk_error: str | None = None

    def _client_ready(self) -> tuple[bool, str]:
        if not self.settings.has_e2b:
            return False, "E2B_API_KEY is not configured"
        try:
            from e2b_desktop import Sandbox  # noqa: F401
        except ImportError:
            return False, "e2b-desktop package is not installed"
        return True, ""

    async def is_available(self) -> bool:
        ok, _ = self._client_ready()
        return ok

    async def capabilities(self) -> ProviderCapabilities:
        ok, msg = self._client_ready()
        return ProviderCapabilities(
            shell=ok,
            files=ok,
            screenshot=ok,
            gui_input=ok,
            browser=ok,
            notes=msg or "E2B Firecracker sandbox",
        )

    def _get_sandbox_class(self) -> Any:
        from e2b_desktop import Sandbox  # type: ignore

        return Sandbox

    async def create(self, conversation_id: str) -> SandboxInfo:
        ok, msg = self._client_ready()
        if not ok:
            return SandboxInfo(
                conversation_id=conversation_id,
                status=SandboxStatus.unavailable,
                provider=self.name,
                message=f"{WORKSPACE_UNAVAILABLE}: {msg}",
            )

        def _create() -> Any:
            Sandbox = self._get_sandbox_class()
            kwargs: dict[str, Any] = {
                "api_key": self.settings.e2b_api_key,
                "timeout": self.settings.e2b_timeout_sec,
            }
            if self.settings.e2b_template_id:
                kwargs["template"] = self.settings.e2b_template_id
            return Sandbox.create(**kwargs)

        try:
            sbx = await asyncio.to_thread(_create)
        except Exception:
            log.exception("E2B create failed")
            return SandboxInfo(
                conversation_id=conversation_id,
                status=SandboxStatus.error,
                provider=self.name,
                message=f"{WORKSPACE_UNAVAILABLE}: E2B create failed; check server logs",
            )

        sandbox_id = (
            getattr(sbx, "sandbox_id", None) or getattr(sbx, "id", None) or str(id(sbx))
        )
        self._sandboxes[conversation_id] = sbx

        # Best-effort workspace layout
        try:
            await self.run_command(
                conversation_id,
                sandbox_id,
                "mkdir -p /workspace/{uploads,artifacts,projects,scratch,home} && "
                "echo 'TUESDAY workspace' > /workspace/README.txt",
                timeout_sec=30,
            )
        except Exception:
            log.warning("E2B workspace layout bootstrap failed", exc_info=True)

        return SandboxInfo(
            conversation_id=conversation_id,
            status=SandboxStatus.running,
            provider=self.name,
            sandbox_id=str(sandbox_id),
            message="E2B sandbox running",
            screen={"width": 1024, "height": 768},
        )

    def _sbx(self, conversation_id: str, provider_ref: str | None) -> Any:
        sbx = self._sandboxes.get(conversation_id)
        if sbx is None:
            raise ProviderError(
                WORKSPACE_UNAVAILABLE, "Sandbox not running in this process"
            )
        return sbx

    async def get(self, conversation_id: str, provider_ref: str | None) -> SandboxInfo:
        sbx = self._sandboxes.get(conversation_id)
        if not sbx:
            ok, msg = self._client_ready()
            return SandboxInfo(
                conversation_id=conversation_id,
                status=SandboxStatus.stopped if ok else SandboxStatus.unavailable,
                provider=self.name,
                sandbox_id=provider_ref,
                message=None if ok else f"{WORKSPACE_UNAVAILABLE}: {msg}",
            )
        sid = (
            getattr(sbx, "sandbox_id", None) or getattr(sbx, "id", None) or provider_ref
        )
        return SandboxInfo(
            conversation_id=conversation_id,
            status=SandboxStatus.running,
            provider=self.name,
            sandbox_id=str(sid) if sid else provider_ref,
            screen={"width": 1024, "height": 768},
        )

    async def start(
        self, conversation_id: str, provider_ref: str | None
    ) -> SandboxInfo:
        if conversation_id in self._sandboxes:
            return await self.get(conversation_id, provider_ref)
        if provider_ref:

            def _connect() -> Any:
                Sandbox = self._get_sandbox_class()
                return Sandbox.connect(
                    sandbox_id=provider_ref,
                    api_key=self.settings.e2b_api_key,
                    timeout=self.settings.e2b_timeout_sec,
                )

            try:
                self._sandboxes[conversation_id] = await asyncio.to_thread(_connect)
                return await self.get(conversation_id, provider_ref)
            except Exception:
                log.warning(
                    "E2B resume failed; creating a replacement sandbox", exc_info=True
                )
        return await self.create(conversation_id)

    async def stop(self, conversation_id: str, provider_ref: str | None) -> SandboxInfo:
        sbx = self._sandboxes.pop(conversation_id, None)
        if sbx is not None:

            def _kill() -> None:
                for meth in ("pause", "close", "kill"):
                    fn = getattr(sbx, meth, None)
                    if callable(fn):
                        try:
                            fn()
                            return
                        except Exception:
                            continue

            await asyncio.to_thread(_kill)
        return SandboxInfo(
            conversation_id=conversation_id,
            status=SandboxStatus.stopped,
            provider=self.name,
            sandbox_id=provider_ref,
            message="E2B sandbox stopped",
        )

    async def destroy(self, conversation_id: str, provider_ref: str | None) -> None:
        sbx = self._sandboxes.pop(conversation_id, None)

        def _destroy() -> None:
            if sbx is not None:
                sbx.kill()
                return
            if provider_ref:
                Sandbox = self._get_sandbox_class()
                Sandbox.kill(
                    sandbox_id=provider_ref,
                    api_key=self.settings.e2b_api_key,
                )

        await asyncio.to_thread(_destroy)

    async def run_command(
        self,
        conversation_id: str,
        provider_ref: str | None,
        command: str,
        *,
        cwd: str | None = None,
        timeout_sec: int = 60,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        sbx = self._sbx(conversation_id, provider_ref)
        timeout = min(timeout_sec, self.settings.sandbox_max_command_timeout_sec)
        work_cmd = command
        if cwd:
            norm = normalize_workspace_path(cwd)
            work_cmd = f"cd {shlex.quote(norm)} && {command}"

        def _run() -> CommandResult:
            # Try common SDK shapes
            if hasattr(sbx, "commands") and hasattr(sbx.commands, "run"):
                result = sbx.commands.run(work_cmd, timeout=timeout)
                stdout = getattr(result, "stdout", "") or ""
                stderr = getattr(result, "stderr", "") or ""
                code = int(
                    getattr(result, "exit_code", getattr(result, "error", 0)) or 0
                )
                return CommandResult(
                    exit_code=code, stdout=str(stdout), stderr=str(stderr)
                )
            if hasattr(sbx, "run_command"):
                result = sbx.run_command(work_cmd)
                return CommandResult(
                    exit_code=int(getattr(result, "exit_code", 0) or 0),
                    stdout=str(getattr(result, "stdout", "") or ""),
                    stderr=str(getattr(result, "stderr", "") or ""),
                )
            # code interpreter
            if hasattr(sbx, "run_code"):
                # fallback: bash via code
                result = sbx.run_code(
                    f"import subprocess\nr=subprocess.run({work_cmd!r}, shell=True, capture_output=True, text=True, timeout={timeout})\nprint(r.stdout)\nprint(r.stderr, file=__import__('sys').stderr)\nraise SystemExit(r.returncode)"
                )
                logs = getattr(result, "logs", None)
                out = ""
                err = ""
                if logs:
                    out = "\n".join(getattr(logs, "stdout", []) or [])
                    err = "\n".join(getattr(logs, "stderr", []) or [])
                return CommandResult(exit_code=0, stdout=out, stderr=err)
            raise ProviderError(
                WORKSPACE_UNAVAILABLE, "E2B SDK has no supported run API"
            )

        try:
            result = await asyncio.to_thread(_run)
        except ProviderError:
            raise
        except Exception as exc:
            log.exception("E2B command failed")
            raise ProviderError(
                WORKSPACE_UNAVAILABLE, "E2B command failed; check server logs"
            ) from exc

        max_out = self.settings.sandbox_max_output_bytes
        truncated = False
        stdout, stderr = result.stdout, result.stderr
        if len(stdout) > max_out:
            stdout = stdout[:max_out]
            truncated = True
        if len(stderr) > max_out:
            stderr = stderr[:max_out]
            truncated = True
        return CommandResult(
            exit_code=result.exit_code,
            stdout=stdout,
            stderr=stderr,
            truncated=truncated,
            timed_out=result.timed_out,
        )

    async def read_file(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
        *,
        max_bytes: int = 1_048_576,
    ) -> bytes:
        sbx = self._sbx(conversation_id, provider_ref)
        norm = normalize_workspace_path(path)

        def _read() -> bytes:
            if hasattr(sbx, "files") and hasattr(sbx.files, "read"):
                data = sbx.files.read(norm)
                if isinstance(data, str):
                    return data.encode("utf-8")
                return bytes(data)
            raise ProviderError(WORKSPACE_UNAVAILABLE, "E2B files.read unavailable")

        data = await asyncio.to_thread(_read)
        limit = min(max_bytes, self.settings.sandbox_max_file_bytes)
        if len(data) > limit:
            raise ProviderError("FILE_TOO_LARGE", f"File exceeds {limit} bytes")
        return data

    async def write_file(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
        data: bytes,
    ) -> None:
        if len(data) > self.settings.sandbox_max_file_bytes:
            raise ProviderError("FILE_TOO_LARGE", "Write exceeds max file size")
        sbx = self._sbx(conversation_id, provider_ref)
        norm = normalize_workspace_path(path)

        def _write() -> None:
            if hasattr(sbx, "files") and hasattr(sbx.files, "write"):
                try:
                    sbx.files.write(norm, data)
                except TypeError:
                    sbx.files.write(norm, data.decode("utf-8", errors="replace"))
                return
            raise ProviderError(WORKSPACE_UNAVAILABLE, "E2B files.write unavailable")

        await asyncio.to_thread(_write)

    async def list_dir(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
    ) -> list[FileEntry]:
        norm = normalize_workspace_path(path)
        result = await self.run_command(
            conversation_id,
            provider_ref,
            f"ls -lan -- {shlex.quote(norm)}",
            timeout_sec=30,
        )
        entries: list[FileEntry] = []
        for line in result.stdout.splitlines():
            if line.startswith("total") or not line.strip():
                continue
            parts = line.split()
            if len(parts) < 9:
                continue
            name = parts[-1]
            if name in {".", ".."}:
                continue
            is_dir = parts[0].startswith("d")
            try:
                size = int(parts[4])
            except ValueError:
                size = 0
            entries.append(
                FileEntry(
                    path=f"{norm.rstrip('/')}/{name}",
                    name=name,
                    is_dir=is_dir,
                    size=size,
                )
            )
        return entries

    async def mkdir(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
    ) -> None:
        norm = normalize_workspace_path(path)
        await self.run_command(
            conversation_id,
            provider_ref,
            f"mkdir -p -- {shlex.quote(norm)}",
            timeout_sec=30,
        )

    async def move_file(
        self,
        conversation_id: str,
        provider_ref: str | None,
        src: str,
        dst: str,
    ) -> None:
        s = normalize_workspace_path(src)
        d = normalize_workspace_path(dst)
        await self.run_command(
            conversation_id,
            provider_ref,
            f"mv -- {shlex.quote(s)} {shlex.quote(d)}",
            timeout_sec=30,
        )

    async def delete_path(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
    ) -> None:
        norm = normalize_workspace_path(path)
        if norm == LOGICAL_ROOT:
            raise ProviderError("FORBIDDEN", "Cannot delete workspace root")
        await self.run_command(
            conversation_id,
            provider_ref,
            f"rm -rf -- {shlex.quote(norm)}",
            timeout_sec=30,
        )

    async def screenshot(
        self,
        conversation_id: str,
        provider_ref: str | None,
    ) -> ScreenshotResult:
        sbx = self._sbx(conversation_id, provider_ref)

        def _shot() -> bytes:
            # e2b-desktop style
            if hasattr(sbx, "screenshot"):
                data = sbx.screenshot()
                if isinstance(data, bytes):
                    return data
                if hasattr(data, "read"):
                    return data.read()
            if hasattr(sbx, "desktop") and hasattr(sbx.desktop, "screenshot"):
                data = sbx.desktop.screenshot()
                if isinstance(data, bytes):
                    return data
            raise ProviderError(
                WORKSPACE_UNAVAILABLE,
                "Screenshot not supported by this E2B template/SDK",
            )

        try:
            data = await asyncio.to_thread(_shot)
        except ProviderError:
            raise
        except Exception as exc:
            log.exception("E2B screenshot failed")
            raise ProviderError(
                WORKSPACE_UNAVAILABLE, "E2B screenshot failed; check server logs"
            ) from exc
        return ScreenshotResult(content_type="image/png", data=data)

    async def click(
        self,
        conversation_id: str,
        provider_ref: str | None,
        x: int,
        y: int,
        *,
        double: bool = False,
    ) -> None:
        sbx = self._sbx(conversation_id, provider_ref)
        method = sbx.double_click if double else sbx.left_click
        await asyncio.to_thread(method, x=x, y=y)

    async def scroll(
        self, conversation_id: str, provider_ref: str | None, amount: int
    ) -> None:
        sbx = self._sbx(conversation_id, provider_ref)
        await asyncio.to_thread(sbx.scroll, amount)

    async def type_text(
        self, conversation_id: str, provider_ref: str | None, text: str
    ) -> None:
        sbx = self._sbx(conversation_id, provider_ref)
        await asyncio.to_thread(sbx.write, text)

    async def keypress(
        self,
        conversation_id: str,
        provider_ref: str | None,
        keys: str | list[str],
    ) -> None:
        sbx = self._sbx(conversation_id, provider_ref)
        await asyncio.to_thread(sbx.press, keys)
