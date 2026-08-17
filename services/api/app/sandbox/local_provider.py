"""Local development sandbox — isolated dirs, not a full VM."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.sandbox.paths import LOGICAL_ROOT, map_to_host, normalize_workspace_path
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

WORKSPACE_SUBDIRS = ("uploads", "artifacts", "projects", "scratch", "home")


class LocalSandboxProvider:
    name = "local"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._states: dict[str, dict] = {}

    def _root_for(self, conversation_id: str) -> Path:
        prefix = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in conversation_id
        )[:40]
        digest = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()[:20]
        return (
            self.settings.tuesday_data_dir
            / "workspaces"
            / f"{prefix or 'conversation'}-{digest}"
        ).resolve()

    def _ensure_layout(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        for sub in WORKSPACE_SUBDIRS:
            (root / sub).mkdir(exist_ok=True)
        readme = root / "README.txt"
        if not readme.exists():
            readme.write_text(
                "TUESDAY local workspace\n"
                "Logical root: /workspace\n"
                "Subdirs: uploads, artifacts, projects, scratch, home\n",
                encoding="utf-8",
            )

    async def is_available(self) -> bool:
        return True

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            shell=True,
            files=True,
            screenshot=True,
            gui_input=False,
            browser=False,
            notes="Local provider uses host subprocess with cwd jail; not production isolation.",
        )

    async def create(self, conversation_id: str) -> SandboxInfo:
        root = self._root_for(conversation_id)
        self._ensure_layout(root)
        ref = str(root)
        self._states[conversation_id] = {
            "ref": ref,
            "status": SandboxStatus.running,
            "created": time.time(),
        }
        return SandboxInfo(
            conversation_id=conversation_id,
            status=SandboxStatus.running,
            provider=self.name,
            sandbox_id=ref,
            message="Local workspace ready",
            screen={"width": 1280, "height": 720},
        )

    async def get(self, conversation_id: str, provider_ref: str | None) -> SandboxInfo:
        st = self._states.get(conversation_id)
        root = Path(provider_ref) if provider_ref else self._root_for(conversation_id)
        if st:
            return SandboxInfo(
                conversation_id=conversation_id,
                status=st["status"],
                provider=self.name,
                sandbox_id=st.get("ref") or str(root),
                screen={"width": 1280, "height": 720},
            )
        if root.exists():
            return SandboxInfo(
                conversation_id=conversation_id,
                status=SandboxStatus.stopped,
                provider=self.name,
                sandbox_id=str(root),
                message="Workspace exists on disk but is stopped",
            )
        return SandboxInfo(
            conversation_id=conversation_id,
            status=SandboxStatus.none,
            provider=self.name,
            message="No workspace yet",
        )

    async def start(
        self, conversation_id: str, provider_ref: str | None
    ) -> SandboxInfo:
        return await self.create(conversation_id)

    async def stop(self, conversation_id: str, provider_ref: str | None) -> SandboxInfo:
        st = self._states.get(conversation_id)
        root = Path(provider_ref) if provider_ref else self._root_for(conversation_id)
        if st:
            st["status"] = SandboxStatus.stopped
        return SandboxInfo(
            conversation_id=conversation_id,
            status=SandboxStatus.stopped,
            provider=self.name,
            sandbox_id=str(root) if root.exists() else None,
            message="Local workspace stopped (files retained)",
        )

    async def destroy(self, conversation_id: str, provider_ref: str | None) -> None:
        self._states.pop(conversation_id, None)
        root = Path(provider_ref) if provider_ref else self._root_for(conversation_id)
        if root.exists() and root.is_dir():
            # only destroy under data/workspaces
            base = (self.settings.tuesday_data_dir / "workspaces").resolve()
            try:
                root.resolve().relative_to(base)
            except ValueError:
                raise ProviderError(
                    "PATH_ESCAPE", "Refusing to destroy path outside workspaces"
                )
            shutil.rmtree(root)

    def _host(self, conversation_id: str, provider_ref: str | None, path: str) -> Path:
        root = Path(provider_ref) if provider_ref else self._root_for(conversation_id)
        if not root.exists():
            self._ensure_layout(root)
        return map_to_host(path, root, logical_root=LOGICAL_ROOT)

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
        if not command or not command.strip():
            raise ProviderError("INVALID_COMMAND", "Command is empty")

        root = Path(provider_ref) if provider_ref else self._root_for(conversation_id)
        self._ensure_layout(root)
        work_cwd = root
        if cwd:
            work_cwd = self._host(conversation_id, provider_ref, cwd)

        max_out = self.settings.sandbox_max_output_bytes
        timeout = min(timeout_sec, self.settings.sandbox_max_command_timeout_sec)

        proc_env = os.environ.copy()
        # Strip obvious secrets from child env
        for k in list(proc_env):
            lk = k.lower()
            if any(
                s in lk for s in ("key", "secret", "token", "password", "nvidia", "e2b")
            ):
                proc_env.pop(k, None)
        proc_env["TUESDAY_WORKSPACE"] = str(root)
        proc_env["HOME"] = str(root / "home")
        if env:
            proc_env.update(env)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(work_cwd),
                env=proc_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=max_out + 1024,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return CommandResult(
                    exit_code=124,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    timed_out=True,
                )
        except OSError as exc:
            return CommandResult(exit_code=127, stdout="", stderr=str(exc))

        def _clip(b: bytes) -> tuple[str, bool]:
            truncated = len(b) > max_out
            data = b[:max_out]
            return data.decode("utf-8", errors="replace"), truncated

        out, t1 = _clip(stdout_b or b"")
        err, t2 = _clip(stderr_b or b"")
        return CommandResult(
            exit_code=int(proc.returncode or 0),
            stdout=out,
            stderr=err,
            truncated=t1 or t2,
        )

    async def read_file(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
        *,
        max_bytes: int = 1_048_576,
    ) -> bytes:
        host = self._host(conversation_id, provider_ref, path)
        if not host.exists() or not host.is_file():
            raise ProviderError("NOT_FOUND", f"File not found: {path}")
        size = host.stat().st_size
        limit = min(max_bytes, self.settings.sandbox_max_file_bytes)
        if size > limit:
            raise ProviderError("FILE_TOO_LARGE", f"File exceeds {limit} bytes")
        return host.read_bytes()

    async def write_file(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
        data: bytes,
    ) -> None:
        if len(data) > self.settings.sandbox_max_file_bytes:
            raise ProviderError("FILE_TOO_LARGE", "Write exceeds max file size")
        host = self._host(conversation_id, provider_ref, path)
        host.parent.mkdir(parents=True, exist_ok=True)
        host.write_bytes(data)

    async def list_dir(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
    ) -> list[FileEntry]:
        host = self._host(conversation_id, provider_ref, path)
        if not host.exists():
            raise ProviderError("NOT_FOUND", f"Directory not found: {path}")
        if not host.is_dir():
            raise ProviderError("NOT_A_DIRECTORY", f"Not a directory: {path}")
        norm = normalize_workspace_path(path)
        entries: list[FileEntry] = []
        for child in sorted(host.iterdir(), key=lambda p: p.name.lower()):
            rel = f"{norm.rstrip('/')}/{child.name}"
            entries.append(
                FileEntry(
                    path=rel,
                    name=child.name,
                    is_dir=child.is_dir(),
                    size=child.stat().st_size if child.is_file() else 0,
                )
            )
        return entries

    async def mkdir(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
    ) -> None:
        host = self._host(conversation_id, provider_ref, path)
        host.mkdir(parents=True, exist_ok=True)

    async def move_file(
        self,
        conversation_id: str,
        provider_ref: str | None,
        src: str,
        dst: str,
    ) -> None:
        sh = self._host(conversation_id, provider_ref, src)
        dh = self._host(conversation_id, provider_ref, dst)
        if not sh.exists():
            raise ProviderError("NOT_FOUND", f"Source not found: {src}")
        dh.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(sh), str(dh))

    async def delete_path(
        self,
        conversation_id: str,
        provider_ref: str | None,
        path: str,
    ) -> None:
        # Refuse deleting workspace root
        norm = normalize_workspace_path(path)
        if norm == LOGICAL_ROOT:
            raise ProviderError("FORBIDDEN", "Cannot delete workspace root")
        host = self._host(conversation_id, provider_ref, path)
        if not host.exists():
            raise ProviderError("NOT_FOUND", f"Path not found: {path}")
        if host.is_dir():
            shutil.rmtree(host)
        else:
            host.unlink()

    async def screenshot(
        self,
        conversation_id: str,
        provider_ref: str | None,
    ) -> ScreenshotResult:
        """Generate a HUD-style placeholder desktop screenshot."""
        root = Path(provider_ref) if provider_ref else self._root_for(conversation_id)
        w, h = 1280, 720
        img = Image.new("RGB", (w, h), (6, 12, 24))
        draw = ImageDraw.Draw(img, "RGBA")

        # grid
        for x in range(0, w, 40):
            draw.line([(x, 0), (x, h)], fill=(20, 40, 70, 80), width=1)
        for y in range(0, h, 40):
            draw.line([(0, y), (w, y)], fill=(20, 40, 70, 80), width=1)

        # panel
        margin = 48
        draw.rectangle(
            [margin, margin, w - margin, h - margin],
            outline=(120, 220, 255, 220),
            width=2,
            fill=(8, 18, 36, 200),
        )
        # corners
        for cx, cy in [
            (margin, margin),
            (w - margin, margin),
            (margin, h - margin),
            (w - margin, h - margin),
        ]:
            draw.line([(cx - 12, cy), (cx + 12, cy)], fill=(180, 240, 255), width=2)
            draw.line([(cx, cy - 12), (cx, cy + 12)], fill=(180, 240, 255), width=2)

        title = "TUESDAY // LOCAL DESKTOP"
        status = f"conversation={conversation_id[:12]}…"
        path_txt = f"root={root}"
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        draw.text((margin + 24, margin + 24), title, fill=(180, 240, 255), font=font)
        draw.text((margin + 24, margin + 56), status, fill=(140, 190, 220), font=font)
        draw.text(
            (margin + 24, margin + 80), path_txt[:90], fill=(100, 150, 180), font=font
        )
        draw.text(
            (margin + 24, h - margin - 48),
            "Screenshot placeholder — E2B provides live XFCE frames",
            fill=(100, 160, 190),
            font=font,
        )

        # list a few files
        y = margin + 120
        if root.exists():
            for child in sorted(root.iterdir())[:12]:
                mark = "[D]" if child.is_dir() else "[F]"
                draw.text(
                    (margin + 32, y),
                    f"{mark} {child.name}",
                    fill=(160, 210, 240),
                    font=font,
                )
                y += 22

        from io import BytesIO

        buf = BytesIO()
        img.save(buf, format="PNG")
        return ScreenshotResult(
            content_type="image/png", data=buf.getvalue(), width=w, height=h
        )

    async def click(self, *args, **kwargs) -> None:
        raise ProviderError(
            WORKSPACE_UNAVAILABLE, "GUI input requires a desktop sandbox provider"
        )

    async def scroll(self, *args, **kwargs) -> None:
        raise ProviderError(
            WORKSPACE_UNAVAILABLE, "GUI input requires a desktop sandbox provider"
        )

    async def type_text(self, *args, **kwargs) -> None:
        raise ProviderError(
            WORKSPACE_UNAVAILABLE, "GUI input requires a desktop sandbox provider"
        )

    async def keypress(self, *args, **kwargs) -> None:
        raise ProviderError(
            WORKSPACE_UNAVAILABLE, "GUI input requires a desktop sandbox provider"
        )
