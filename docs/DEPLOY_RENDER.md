# Deploy the backend on Render

The root `render.yaml` defines a Docker web service and a managed PostgreSQL database using Render's free instance types. This avoids a paid service plan for evaluation and personal use. It is not an always-on production topology: the web service can spin down when idle, and a free Render Postgres database expires after 30 days.

## 1. Prepare GitHub

Create an empty private repository, then from this repository run:

```bash
git remote add origin git@github.com:YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

GitHub Actions must be green before deployment. The repository contains no `.env`, local databases, signing keys, or built packages.

## 2. Create secrets

Generate a high-entropy owner value locally:

```bash
openssl rand -hex 32   # use as TUESDAY_ACCESS_TOKEN
```

`TUESDAY_SECRET_KEY` is generated automatically by the Blueprint. Obtain fresh server-side keys from NVIDIA and E2B. Revoke any key previously posted in chat, logs, screenshots, or commits.

## 3. Apply the Blueprint

1. In Render, choose **New → Blueprint** and connect the GitHub repository.
2. Confirm that both resources use the `free` plan and choose the same region.
3. Enter the prompted values for `TUESDAY_ACCESS_TOKEN`, `NVIDIA_API_KEY`, and `E2B_API_KEY`.
4. Apply the Blueprint. Free web services do not support Render's `preDeployCommand`, so the container runs `alembic upgrade head` immediately before starting Uvicorn.

The service automatically receives the PostgreSQL connection string and Render's `PORT`. Production validation refuses to start if the database, credentials, access controls, or sandbox provider are unsafe.

The free database is temporary. Export any data you need before its 30-day expiration, or move the database to Neon or a paid Render plan. Upgrade the web service before relying on availability guarantees.

If you add a custom domain, append its hostname to `TUESDAY_ALLOWED_HOSTS` before sending traffic to it.

## 4. Verify

Replace the example origin below:

```bash
curl --fail https://your-service.onrender.com/health/live
curl --fail https://your-service.onrender.com/health/ready
```

Open the origin, enter `TUESDAY_ACCESS_TOKEN`, then complete every live check in [`PRODUCTION_CHECKLIST.md`](PRODUCTION_CHECKLIST.md). Health passing proves the process and database are available; it does not prove that paid third-party APIs accept the supplied credentials.

## Optional speech

Fish Audio synthesis can be enabled in the Render environment:

```text
TTS_PROVIDER=fish
FISH_AUDIO_API_KEY=<secret>
FISH_AUDIO_VOICE_ID=<optional model/reference id>
```

Speech-to-text is intentionally endpoint-configurable because NVIDIA speech deployments expose different endpoints. Set `STT_PROVIDER`, the exact `STT_API_URL` supplied by NVIDIA, and `STT_MODEL`; otherwise leave it disabled. The backend never sends the NVIDIA key to clients.

## Operations

- Configure Render deploys to require successful GitHub checks, as expressed by `autoDeployTrigger: checksPass`.
- Expect a cold start after the free web service has been idle. Free-instance availability is suitable for evaluation, not an uptime commitment.
- Back up or migrate PostgreSQL data before the free database expires after 30 days.
- Watch `/health/ready`, application errors, PostgreSQL capacity, and E2B usage.
- Database records persist in PostgreSQL. Temporary upload staging under `/tmp` may be lost on a restart; durable artifacts belong in the remote E2B workspace or a future object-storage adapter.
- Roll back the web service from Render if a deployment fails, but never downgrade the database without reviewing the migration first.

Official references: [Render Blueprint specification](https://render.com/docs/blueprint-spec), [FastAPI deployment guide](https://render.com/docs/deploy-fastapi), and [Render PostgreSQL](https://render.com/docs/postgresql-creating-connecting).
