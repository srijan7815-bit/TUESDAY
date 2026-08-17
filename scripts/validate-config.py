#!/usr/bin/env python3
"""Validate deployment, workflow, Android XML, and PWA file references."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

import yaml

ROOT = Path(__file__).resolve().parents[1]


def yaml_mapping(path: Path) -> dict:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a YAML mapping")
    return value


def main() -> int:
    render = yaml_mapping(ROOT / "render.yaml")
    if not render.get("services") or not render.get("databases"):
        raise ValueError("render.yaml must define a web service and database")
    service = render["services"][0]
    if service.get("healthCheckPath") != "/health/ready":
        raise ValueError("Render readiness path is missing")
    env = {item["key"]: item for item in service.get("envVars", [])}
    for secret in ("TUESDAY_ACCESS_TOKEN", "NVIDIA_API_KEY", "E2B_API_KEY"):
        if env.get(secret, {}).get("sync") != "false":
            raise ValueError(f"{secret} must be a non-synced Render secret")

    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        yaml_mapping(path)
    yaml_mapping(ROOT / ".github" / "dependabot.yml")

    for path in sorted((ROOT / "clients" / "android" / "app" / "src").glob("**/*.xml")):
        ElementTree.parse(path)

    static = ROOT / "services" / "api" / "app" / "static"
    manifest = json.loads((static / "manifest.webmanifest").read_text(encoding="utf-8"))
    for icon in manifest.get("icons", []):
        source = str(icon["src"])
        if not source.startswith("/static/"):
            raise ValueError(f"Unexpected PWA icon path: {source}")
        target = static / source.removeprefix("/static/")
        if not target.is_file():
            raise ValueError(f"Missing PWA icon: {target.relative_to(ROOT)}")

    print("Deployment, workflow, Android XML, and PWA configuration passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
