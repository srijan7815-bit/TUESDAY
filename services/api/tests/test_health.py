import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "TUESDAY"
    assert data["capabilities"]["mock_model"] is True
    assert data["capabilities"]["sandbox_provider"] == "local"


@pytest.mark.asyncio
async def test_index_serves_hud(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "TUESDAY" in r.text
    assert "Communications" in r.text
    assert "Remote workspace" in r.text
    assert "System notification" in r.text
    assert 'id="btn-new-session"' in r.text
    assert 'id="btn-motion"' in r.text
