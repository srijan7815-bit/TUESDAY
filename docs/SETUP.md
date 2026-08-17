# Development setup

## Requirements

- Python 3.12
- Node.js 22 for JavaScript syntax checks
- Docker for container checks (optional)
- JDK 17 and Android SDK 36 for local Android builds (optional)
- `dpkg-deb`, Python 3, and a supported browser for Linux Lite packaging

## API and PWA

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r services/api/requirements-dev.txt
cp .env.example .env
./scripts/dev.sh
```

Open `http://localhost:8000`. Set a long `TUESDAY_ACCESS_TOKEN` if you want the local login gate. With no NVIDIA key, the UI clearly uses a mock response stream. `SANDBOX_PROVIDER=local` uses per-conversation directories but is not a security boundary and is refused in production.

## Local quality gate

```bash
./scripts/check.sh
```

This runs Python compilation, Ruff, MyPy, the API suite, browser script parsing, shell parsing, a full Alembic upgrade/downgrade/upgrade, credential-pattern scanning, and the Linux `.deb` build.

## Docker Compose

```bash
docker compose up --build
```

The Compose profile is for local development and keeps SQLite data in a named volume. Render production uses managed PostgreSQL.

## Provider configuration

| Feature | Variables | Development behavior when absent | Production behavior |
|---|---|---|---|
| Chat/agent | `NVIDIA_API_KEY` | Explicit mock when enabled | Startup fails |
| Remote desktop | `SANDBOX_PROVIDER=e2b`, `E2B_API_KEY` | Local provider available | Startup fails without E2B |
| Speech-to-text | `STT_PROVIDER`, `STT_API_URL`, `STT_MODEL` | Disabled | Disabled unless configured |
| Speech synthesis | `TTS_PROVIDER=fish`, `FISH_AUDIO_API_KEY`, optional voice ID | Disabled | Disabled unless configured |
| Owner login | `TUESDAY_ACCESS_TOKEN`, `TUESDAY_SECRET_KEY` | Optional | Startup fails if weak/missing |

Use `.env.example` as the complete variable reference. Never add live keys to an Android resource, Gradle property, JavaScript file, Linux package, or Git commit.
