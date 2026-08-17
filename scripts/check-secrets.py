#!/usr/bin/env python3
"""Fail when committed source contains a credential-shaped value."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "NVIDIA key": re.compile(rb"nvapi-[A-Za-z0-9_-]{16,}"),
    "E2B key": re.compile(rb"e2b_[A-Za-z0-9]{20,}"),
    "GitHub token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "OpenAI key": re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / raw.decode("utf-8") for raw in result.stdout.split(b"\0") if raw]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        content = path.read_bytes()
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(ROOT)}: possible {label}")
    if findings:
        print("Credential scan failed:")
        print("\n".join(f"- {finding}" for finding in findings))
        return 1
    print("Credential scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
