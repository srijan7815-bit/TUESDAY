# TUESDAY

Private agentic AI console with a FastAPI backend, responsive installable HUD, conversation-scoped E2B desktop workspaces, memory controls, approvals, attachments, optional speech, and thin Android and Linux Lite clients.

## What is included

- Production-gated FastAPI service with PostgreSQL migrations, session authentication, request limits, security headers, readiness checks, and a non-root container.
- NVIDIA OpenAI-compatible chat streaming and tool calling. Mock responses are development-only and the server refuses to start with them enabled in production.
- E2B Desktop provider for remote shell, files, screenshots, mouse, keyboard, persistence, and idle pause. The local provider is restricted to development.
- One-use approval gates for shell commands, destructive file operations, and remote GUI input.
- Responsive PWA with login, chat, workspace controls, uploads/downloads, push-to-talk, voice playback, memory, and offline shell.
- Android 8+ client targeting API 36 with an HTTPS-only release WebView, same-origin policy, microphone/file flows, and protected artifact downloads.
- Lightweight Linux Lite `.deb` that uses the maintained system browser in application mode and stores only the backend URL.
- GitHub Actions for linting, tests, migrations, Android APK, Linux package, credential scanning, and signed tagged releases.
- Render Blueprint for a paid web service and managed PostgreSQL. Paid plans are intentional: production data and availability must not depend on an ephemeral free instance.

## Repository map

```text
services/api/       FastAPI service, HUD, providers, migrations, tests
clients/android/    Native Android secure WebView application
clients/linux/      Linux Lite launcher and Debian package builder
.github/workflows/  CI and signed release automation
docs/               deployment, release, and verification guides
render.yaml         Render Blueprint
```

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r services/api/requirements-dev.txt
cp .env.example .env
./scripts/dev.sh
```

Open `http://localhost:8000`. Development works without provider credentials: chat is explicitly labeled as mock and workspaces use the local provider. These fallbacks cannot pass production startup validation.

Run the full local quality gate:

```bash
./scripts/check.sh
```

## Deploy and build

1. Follow [`docs/DEPLOY_RENDER.md`](docs/DEPLOY_RENDER.md) to create the Render Blueprint and set the NVIDIA, E2B, and owner access secrets.
2. Push the repository to GitHub. Pull requests run all four CI jobs.
3. Download the debug APK and Linux package from a successful CI run, or configure Android signing and create a `v1.0.0` tag for release artifacts.
4. Give both clients the resulting `https://…onrender.com` origin, then log in with `TUESDAY_ACCESS_TOKEN`.

Client and release details are in [`docs/RELEASE.md`](docs/RELEASE.md).

## Security model

- Provider keys and the owner token are server-side environment variables only.
- Browser login is exchanged for a signed, `HttpOnly`, `Secure`, `SameSite=Strict` cookie.
- Production startup fails on weak secrets, SQLite, local sandboxing, wildcard CORS, missing NVIDIA/E2B credentials, or mock mode.
- Paths are normalized below `/workspace`; remote provider identifiers are never accepted from clients.
- Consequential tool authorization is exact and single-use.
- Speech features fail closed until their provider endpoint and credentials are configured.

See [`SECURITY.md`](SECURITY.md) before exposing a deployment to the internet.

## Verification boundary

The repository is locally testable without credentials. Live NVIDIA inference, E2B desktop operations, Fish Audio, optional NVIDIA STT, Render deployment, and Android release signing require the corresponding account secrets. Do not call those integrations verified until the live checklist in [`docs/PRODUCTION_CHECKLIST.md`](docs/PRODUCTION_CHECKLIST.md) passes.

## License

Proprietary. See [`LICENSE`](LICENSE).
