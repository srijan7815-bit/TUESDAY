"""Path normalization and traversal guards for workspace roots."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path, PurePosixPath

from app.sandbox.provider import ProviderError

# Logical workspace root inside every sandbox
LOGICAL_ROOT = "/workspace"

_SAFE_REL = re.compile(r"^[A-Za-z0-9._\- /]+$")


def normalize_workspace_path(user_path: str, *, root: str = LOGICAL_ROOT) -> str:
    """Return a normalized absolute POSIX path under root, or raise."""
    if user_path is None or str(user_path).strip() == "":
        raise ProviderError("INVALID_PATH", "Path is required")

    raw = str(user_path).strip().replace("\\", "/")

    # Block null bytes and oddities
    if "\x00" in raw:
        raise ProviderError("INVALID_PATH", "Null byte in path")

    # Absolute host-like paths outside workspace
    if raw.startswith("//") or re.match(r"^[A-Za-z]:", raw):
        raise ProviderError("INVALID_PATH", "Host absolute paths are not allowed")

    if raw.startswith("/"):
        if not (raw == root or raw.startswith(root + "/")):
            # allow bare "/" meaning root
            if raw == "/":
                raw = root
            else:
                raise ProviderError(
                    "PATH_ESCAPE",
                    f"Path must be under {root}",
                )
        candidate = raw
    else:
        candidate = f"{root.rstrip('/')}/{raw.lstrip('/')}"

    pure = PurePosixPath(candidate)
    # Resolve . and .. without filesystem
    parts: list[str] = []
    for p in pure.parts:
        if p in ("", "/"):
            continue
        if p == ".":
            continue
        if p == "..":
            if not parts:
                raise ProviderError("PATH_ESCAPE", "Path traversal rejected")
            parts.pop()
            continue
        parts.append(p)

    normalized = "/" + "/".join(parts) if parts else "/"
    # Ensure still under root
    root_pure = PurePosixPath(root)
    norm_pure = PurePosixPath(normalized)
    try:
        norm_pure.relative_to(root_pure)
    except ValueError as exc:
        if normalized != root:
            raise ProviderError("PATH_ESCAPE", "Path escapes workspace root") from exc

    return normalized if normalized != "/" else root


def map_to_host(
    normalized_posix: str, host_root: Path, *, logical_root: str = LOGICAL_ROOT
) -> Path:
    """Map a logical /workspace/... path onto a host directory."""
    norm = normalize_workspace_path(normalized_posix, root=logical_root)
    rel = norm[len(logical_root) :].lstrip("/")
    host_root = host_root.resolve()
    if rel:
        target = (host_root / rel).resolve()
    else:
        target = host_root
    try:
        target.relative_to(host_root)
    except ValueError as exc:
        raise ProviderError("PATH_ESCAPE", "Resolved path escapes host root") from exc
    return target


def ensure_under(host_path: Path, host_root: Path) -> Path:
    host_root = host_root.resolve()
    resolved = host_path.resolve()
    try:
        resolved.relative_to(host_root)
    except ValueError as exc:
        raise ProviderError("PATH_ESCAPE", "Path escapes host root") from exc
    return resolved


def is_blocked_network_target(host: str) -> bool:
    """Return True if host should be blocked by default network policy."""
    h = host.strip().lower().strip("[]")
    if h in {"localhost", "metadata.google.internal"} or h.endswith(".localhost"):
        return True
    if h.endswith((".local", ".internal")):
        return True
    try:
        address = ipaddress.ip_address(h)
    except ValueError:
        return False
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
