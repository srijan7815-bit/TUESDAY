# Implementation status

**Prepared:** 2026-08-17
**Release candidate:** 1.0.0 source

## Implemented

| Area | State |
|---|---|
| FastAPI / PWA | Implemented with auth, rate and size limits, security headers, readiness, chat/tool streaming, memory, uploads, voice proxies, approval UI, and offline shell |
| Database | PostgreSQL-ready async SQLAlchemy plus Alembic initial migration; SQLite development mode |
| Models | NVIDIA OpenAI-compatible adapter, development mock blocked in production |
| Remote desktop | Current E2B Desktop adapter with lifecycle, shell, files, screenshots, and GUI input; idle reaper |
| Safety | One-use exact approvals, workspace path jail, server-only credentials, production fail-closed validation |
| Render | Free preview Blueprint, managed PostgreSQL, non-root Docker image, migration-on-start, readiness health path |
| Android | API 26–36 native client source, URL policy tests, secure WebView, CI APK and signed tag workflow |
| Linux Lite | HTTPS-only system-browser launcher, desktop entry, installable `.deb`, checksum and release workflow |
| GitHub | CI, release workflow, Dependabot, credential scan, contribution and security policy |

## Verified locally

The final local gate completed with 44 passing backend/provider tests, clean Ruff and MyPy checks, browser JavaScript parsing, Alembic upgrade/downgrade/upgrade, deployment/XML/PWA validation, credential scanning, and reproducible Linux package construction.

## Requires owner credentials or external infrastructure

- Live NVIDIA inference and tool-call behavior.
- Live E2B create/resume/pause and desktop input behavior.
- Optional Fish Audio synthesis and configured NVIDIA speech endpoint.
- Render Blueprint creation and public HTTPS checks.
- Android SDK build in GitHub/Android Studio and release signing on the owner's keystore.
- Physical/emulator Android matrix and Linux Lite installation matrix.

These items are not truthfully verifiable in a credential-free local workspace. Use [`PRODUCTION_CHECKLIST.md`](PRODUCTION_CHECKLIST.md) after deployment.
