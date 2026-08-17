"""Pytest fixtures for TUESDAY API tests."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Configure env before app import
_TMP = tempfile.mkdtemp(prefix="tuesday_test_")
os.environ["TUESDAY_DATA_DIR"] = _TMP
os.environ["TUESDAY_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP}/test.db"
os.environ["STORAGE_LOCAL_PATH"] = f"{_TMP}/storage"
os.environ["SANDBOX_PROVIDER"] = "local"
os.environ["SANDBOX_MAX_CONCURRENT"] = "50"
os.environ["TUESDAY_ALLOW_MOCK_MODEL"] = "true"
os.environ["NVIDIA_API_KEY"] = ""
os.environ["E2B_API_KEY"] = ""
os.environ["TUESDAY_SECRET_KEY"] = "test-secret"
os.environ["TUESDAY_ACCESS_TOKEN"] = ""
os.environ["REQUIRE_APPROVAL_FOR_SHELL"] = "false"
os.environ["REQUIRE_APPROVAL_FOR_DESTRUCTIVE"] = "false"
os.environ["REQUIRE_APPROVAL_FOR_GUI"] = "false"

from app.core.config import get_settings  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.sandbox.local_provider import LocalSandboxProvider  # noqa: E402
from app.sandbox.manager import WorkspaceManager, reset_workspace_manager  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_settings_and_manager() -> Iterator[None]:
    get_settings.cache_clear()
    settings = get_settings()
    settings.ensure_dirs()
    reset_workspace_manager(
        WorkspaceManager(provider=LocalSandboxProvider(settings), settings=settings)
    )
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def data_dir() -> Path:
    return Path(os.environ["TUESDAY_DATA_DIR"])
