"""TUESDAY FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import __version__
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.security import RequestGuardsMiddleware
from app.db.session import init_db, session_scope
from app.routes import approvals, auth, chat, media, memory, workspaces
from app.sandbox.manager import get_workspace_manager

log = get_logger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"


async def _idle_reaper() -> None:
    """Stop forgotten remote desktops without blocking request handling."""
    while True:
        await asyncio.sleep(60)
        try:
            async for session in session_scope():
                stopped = await get_workspace_manager().idle_reap(session)
                if stopped:
                    log.info("stopped %s idle workspace(s)", stopped)
                break
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("workspace idle reaper failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.tuesday_log_level)
    settings.ensure_dirs()
    settings.validate_runtime()
    await init_db()
    log.info(
        "TUESDAY starting env=%s provider=%s nvidia=%s",
        settings.tuesday_env,
        settings.sandbox_provider,
        "yes" if settings.has_nvidia else "mock",
    )
    reaper = asyncio.create_task(_idle_reaper(), name="tuesday-workspace-idle-reaper")
    try:
        yield
    finally:
        reaper.cancel()
        with suppress(asyncio.CancelledError):
            await reaper
    log.info("TUESDAY shutdown")


app = FastAPI(
    title="TUESDAY",
    version=__version__,
    description="Personal agentic AI assistant",
    lifespan=lifespan,
    docs_url="/docs" if get_settings().tuesday_env != "production" else None,
    redoc_url=None,
)

settings = get_settings()
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestGuardsMiddleware)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(workspaces.router)
app.include_router(memory.router)
app.include_router(approvals.router)
app.include_router(media.router)


@app.get("/health")
async def health():
    s = get_settings()
    return {
        "status": "ok",
        "service": "TUESDAY",
        "version": __version__,
        "env": s.tuesday_env,
        "capabilities": {
            "nvidia": s.has_nvidia,
            "mock_model": (not s.has_nvidia) and s.tuesday_allow_mock_model,
            "sandbox_provider": s.sandbox_provider,
            "e2b_configured": s.has_e2b,
            "memory": s.memory_enabled,
            "stt": s.stt_provider,
            "tts": s.tts_provider,
            "proactive_notifications": s.proactive_notifications_enabled,
        },
    }


@app.get("/health/live")
async def liveness():
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness():
    try:
        async for session in session_scope():
            await session.execute(text("SELECT 1"))
            break
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)
    return {"status": "ready"}


@app.get("/")
async def index():
    index_path = STATIC_DIR / "index.html"
    return FileResponse(index_path)


@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(
        STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json"
    )


@app.get("/service-worker.js")
async def service_worker():
    return FileResponse(
        STATIC_DIR / "service-worker.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/offline.html")
async def offline():
    return FileResponse(STATIC_DIR / "offline.html")


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
