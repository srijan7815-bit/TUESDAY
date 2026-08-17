import json

import pytest


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    event = "message"
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif line.strip() == "":
            if data_lines:
                raw = "\n".join(data_lines)
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {"raw": raw}
                events.append((event, payload))
            event = "message"
            data_lines = []
    if data_lines:
        raw = "\n".join(data_lines)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        events.append((event, payload))
    return events


@pytest.mark.asyncio
async def test_chat_stream_mock(client):
    r = await client.post(
        "/v1/chat/stream",
        json={
            "messages": [{"role": "user", "content": "Hello TUESDAY"}],
            "enable_tools": False,
        },
    )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    types = [e for e, _ in events]
    assert "session" in types
    assert "delta" in types or "done" in types
    # Must not claim real Nemotron without key
    metas = [d for e, d in events if e == "meta"]
    for m in metas:
        model = str(m.get("model") or "")
        assert "mock" in model or m.get("provider") == "mock"


@pytest.mark.asyncio
async def test_chat_tool_loop_list_workspace(client):
    r = await client.post(
        "/v1/chat/stream",
        json={
            "conversation_id": "conv-tools-1",
            "messages": [{"role": "user", "content": "list workspace"}],
            "enable_tools": True,
        },
    )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    types = [e for e, _ in events]
    assert "tool_start" in types
    assert "tool_result" in types
    results = [d for e, d in events if e == "tool_result"]
    assert results
    assert results[0]["name"] == "computer_list_dir"
    assert results[0]["result"]["ok"] is True


@pytest.mark.asyncio
async def test_memory_crud(client):
    r = await client.post(
        "/v1/memory/remember",
        json={"content": "User likes cyan HUD", "kind": "preference", "key": "theme"},
    )
    assert r.status_code == 200
    entry_id = r.json()["entry"]["id"]

    listed = await client.get("/v1/memory")
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1

    dis = await client.post(f"/v1/memory/{entry_id}/enabled", json={"enabled": False})
    assert dis.status_code == 200
    assert dis.json()["entry"]["enabled"] is False

    exp = await client.get("/v1/memory/export")
    assert exp.status_code == 200
    assert exp.json()["count"] >= 1

    gone = await client.delete(f"/v1/memory/{entry_id}")
    assert gone.status_code == 200
    assert gone.json()["ok"] is True


@pytest.mark.asyncio
async def test_approval_flow(client):
    c = await client.post(
        "/v1/approvals",
        json={
            "conversation_id": "c1",
            "action": "network",
            "summary": "Allow curl example.com",
            "details": {"host": "example.com"},
        },
    )
    assert c.status_code == 200
    aid = c.json()["id"]
    assert c.json()["status"] == "pending"

    r = await client.post(f"/v1/approvals/{aid}", json={"decision": "approved"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
