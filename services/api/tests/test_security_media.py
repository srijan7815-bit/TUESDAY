"""Production guardrails, authentication, PWA, and media integration tests."""

from __future__ import annotations

import pytest

from app.core.config import Settings, get_settings
from app.core.security import create_session_cookie, verify_session_cookie
from app.sandbox.local_provider import LocalSandboxProvider
from app.sandbox.manager import WorkspaceManager, reset_workspace_manager


def test_session_cookie_is_signed_and_expires():
    settings = Settings(
        _env_file=None,
        tuesday_secret_key="x" * 48,
        tuesday_session_ttl_sec=60,
    )
    cookie = create_session_cookie(settings, now=1_000)
    assert verify_session_cookie(cookie, settings, now=1_059)
    assert not verify_session_cookie(cookie + "tampered", settings, now=1_059)
    assert not verify_session_cookie(cookie, settings, now=1_061)


def test_unsafe_production_configuration_fails_closed():
    settings = Settings(_env_file=None, tuesday_env="production")
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        settings.validate_runtime()


def test_valid_production_configuration_passes():
    settings = Settings(
        _env_file=None,
        tuesday_env="production",
        tuesday_secret_key="s" * 48,
        tuesday_access_token="a" * 32,
        tuesday_allow_mock_model=False,
        tuesday_database_url="postgresql+asyncpg://user:pass@db.example/tuesday",
        nvidia_api_key="nvapi-test-value",
        sandbox_provider="e2b",
        e2b_api_key="e2b_test_value",
        tuesday_cors_origins="https://tuesday.example",
    )
    settings.validate_runtime()


@pytest.mark.asyncio
async def test_security_headers_and_pwa_files(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]

    manifest = await client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    assert manifest.json()["display"] == "standalone"
    worker = await client.get("/service-worker.js")
    assert worker.status_code == 200
    assert worker.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_authentication_round_trip(client, monkeypatch):
    monkeypatch.setenv("TUESDAY_ACCESS_TOKEN", "test-access-token-with-safe-length")
    monkeypatch.setenv("TUESDAY_SECRET_KEY", "test-session-secret-that-is-long-enough")
    get_settings.cache_clear()

    protected = await client.get("/v1/memory")
    assert protected.status_code == 401

    status = await client.get("/v1/auth/status")
    assert status.json() == {"auth_required": True, "authenticated": False}
    rejected = await client.post("/v1/auth/session", json={"token": "wrong"})
    assert rejected.status_code == 401
    accepted = await client.post(
        "/v1/auth/session", json={"token": "test-access-token-with-safe-length"}
    )
    assert accepted.status_code == 200
    assert "httponly" in accepted.headers["set-cookie"].lower()
    assert (await client.get("/v1/memory")).status_code == 200

    assert (await client.delete("/v1/auth/session")).status_code == 200
    assert (await client.get("/v1/memory")).status_code == 401


@pytest.mark.asyncio
async def test_attachment_upload_and_type_rejection(client):
    uploaded = await client.post(
        "/v1/media/attachments",
        data={"conversation_id": "conv-upload"},
        files={"file": ("notes.md", b"safe notes", "text/markdown")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["path"] == "/workspace/uploads/notes.md"

    rejected = await client.post(
        "/v1/media/attachments",
        data={"conversation_id": "conv-upload"},
        files={"file": ("program.exe", b"MZ", "application/x-msdownload")},
    )
    assert rejected.status_code == 415


@pytest.mark.asyncio
async def test_shell_approval_is_single_use(client, monkeypatch):
    monkeypatch.setenv("REQUIRE_APPROVAL_FOR_SHELL", "true")
    get_settings.cache_clear()
    settings = get_settings()
    reset_workspace_manager(
        WorkspaceManager(provider=LocalSandboxProvider(settings), settings=settings)
    )
    conversation_id = "conv-approval-once"
    endpoint = f"/v1/conversations/{conversation_id}/workspace/execute"
    body = {"command": "printf approved"}

    first = await client.post(endpoint, json=body)
    assert first.status_code == 409
    approval_id = first.json()["detail"]["approval_id"]
    resolved = await client.post(
        f"/v1/approvals/{approval_id}", json={"decision": "approved"}
    )
    assert resolved.status_code == 200

    executed = await client.post(endpoint, json=body)
    assert executed.status_code == 200
    assert executed.json()["stdout"] == "approved"

    third = await client.post(endpoint, json=body)
    assert third.status_code == 409
    assert third.json()["detail"]["approval_id"] != approval_id
