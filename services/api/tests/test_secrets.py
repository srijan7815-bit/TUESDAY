"""Ensure secrets are not reflected in health or public workspace DTOs."""

import pytest


@pytest.mark.asyncio
async def test_health_has_no_secrets(client, monkeypatch):
    nvidia_secret = "example-nvidia-secret-do-not-leak"
    e2b_secret = "example-sandbox-secret-do-not-leak"
    monkeypatch.setenv("NVIDIA_API_KEY", nvidia_secret)
    monkeypatch.setenv("E2B_API_KEY", e2b_secret)
    from app.core.config import get_settings

    get_settings.cache_clear()

    r = await client.get("/health")
    text = r.text
    assert nvidia_secret not in text
    assert e2b_secret not in text
    body = r.json()
    assert "nvidia_api_key" not in body
    assert "e2b_api_key" not in body


@pytest.mark.asyncio
async def test_workspace_dto_no_credentials(client):
    cid = "conv-sec-1"
    r = await client.post(f"/v1/conversations/{cid}/workspace/start")
    body = r.json()
    blob = str(body).lower()
    assert "api_key" not in blob
    assert "authorization" not in blob
    # The local development provider returns its jailed path, never a provider credential.
    assert body.get("provider") == "local"
