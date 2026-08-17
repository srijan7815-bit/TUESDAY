"""Workspace isolation, reuse, files, commands, screenshots, path guards."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_workspace_lazy_status(client):
    cid = "conv-lazy-1"
    r = await client.get(f"/v1/conversations/{cid}/workspace")
    assert r.status_code == 200
    body = r.json()
    assert body["conversation_id"] == cid
    assert body["status"] in {"none", "stopped"}
    assert "capabilities" in body


@pytest.mark.asyncio
async def test_workspace_start_stop_reuse(client):
    cid = "conv-reuse-1"
    r = await client.post(f"/v1/conversations/{cid}/workspace/start")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert body["provider"] == "local"
    ref = body.get("sandbox_id")
    assert ref

    r2 = await client.post(f"/v1/conversations/{cid}/workspace/start")
    assert r2.status_code == 200
    assert r2.json()["status"] == "running"

    r3 = await client.post(f"/v1/conversations/{cid}/workspace/stop")
    assert r3.status_code == 200
    assert r3.json()["status"] == "stopped"

    # files retained — start again
    r4 = await client.post(f"/v1/conversations/{cid}/workspace/start")
    assert r4.status_code == 200
    assert r4.json()["status"] == "running"

    restarted = await client.post(f"/v1/conversations/{cid}/workspace/restart")
    assert restarted.status_code == 200
    assert restarted.json()["status"] == "running"


@pytest.mark.asyncio
async def test_workspace_destroy_removes_files(client):
    cid = "conv-destroy-1"
    await client.post(f"/v1/conversations/{cid}/workspace/start")
    await client.post(
        f"/v1/conversations/{cid}/workspace/files/write",
        json={"path": "/workspace/scratch/delete-me.txt", "content": "temporary"},
    )
    destroyed = await client.delete(f"/v1/conversations/{cid}/workspace")
    assert destroyed.status_code == 200
    status = await client.get(f"/v1/conversations/{cid}/workspace")
    assert status.json()["status"] == "none"


@pytest.mark.asyncio
async def test_isolation_two_conversations(client):
    # Both names sanitize to the same human-readable prefix; the hash must keep
    # their local development roots distinct.
    a, b = "conv-iso:*", "conv-iso@*"
    await client.post(f"/v1/conversations/{a}/workspace/start")
    await client.post(f"/v1/conversations/{b}/workspace/start")

    await client.post(
        f"/v1/conversations/{a}/workspace/files/write",
        json={"path": "/workspace/secret-a.txt", "content": "alpha-only"},
    )
    await client.post(
        f"/v1/conversations/{b}/workspace/files/write",
        json={"path": "/workspace/secret-b.txt", "content": "beta-only"},
    )

    la = await client.get(
        f"/v1/conversations/{a}/workspace/files", params={"path": "/workspace"}
    )
    names_a = {e["name"] for e in la.json()["entries"]}
    assert "secret-a.txt" in names_a
    assert "secret-b.txt" not in names_a

    # B cannot read A's file via path
    rb = await client.get(
        f"/v1/conversations/{b}/workspace/files/content",
        params={"path": "/workspace/secret-a.txt"},
    )
    assert rb.status_code == 404


@pytest.mark.asyncio
async def test_file_ops_and_execute(client):
    cid = "conv-files-1"
    await client.post(f"/v1/conversations/{cid}/workspace/start")

    w = await client.post(
        f"/v1/conversations/{cid}/workspace/files/write",
        json={"path": "/workspace/projects/hello.py", "content": "print('hi')\n"},
    )
    assert w.status_code == 200

    r = await client.get(
        f"/v1/conversations/{cid}/workspace/files/content",
        params={"path": "/workspace/projects/hello.py"},
    )
    assert r.status_code == 200
    assert r.content == b"print('hi')\n"

    ex = await client.post(
        f"/v1/conversations/{cid}/workspace/execute",
        json={"command": "python3 hello.py", "cwd": "/workspace/projects"},
    )
    assert ex.status_code == 200
    body = ex.json()
    assert body["exit_code"] == 0
    assert "hi" in body["stdout"]


@pytest.mark.asyncio
async def test_path_traversal_rejected(client):
    cid = "conv-trav-1"
    await client.post(f"/v1/conversations/{cid}/workspace/start")
    r = await client.get(
        f"/v1/conversations/{cid}/workspace/files/content",
        params={"path": "/workspace/../../etc/passwd"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["code"] in {"PATH_ESCAPE", "INVALID_PATH"}


@pytest.mark.asyncio
async def test_screenshot(client):
    cid = "conv-shot-1"
    await client.post(f"/v1/conversations/{cid}/workspace/start")
    r = await client.get(f"/v1/conversations/{cid}/workspace/screenshot")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_delete_root_forbidden(client):
    cid = "conv-del-1"
    await client.post(f"/v1/conversations/{cid}/workspace/start")
    r = await client.delete(
        f"/v1/conversations/{cid}/workspace/files",
        params={"path": "/workspace"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_command_timeout(client):
    cid = "conv-timeout-1"
    await client.post(f"/v1/conversations/{cid}/workspace/start")
    r = await client.post(
        f"/v1/conversations/{cid}/workspace/execute",
        json={"command": "sleep 5", "timeout_sec": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["timed_out"] is True
    assert body["exit_code"] == 124
