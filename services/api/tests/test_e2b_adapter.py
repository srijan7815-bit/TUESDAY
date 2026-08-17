"""Credential-free contract tests for the installed E2B Desktop adapter."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.sandbox.e2b_provider import E2BSandboxProvider


class _CommandResult:
    exit_code = 0
    stdout = ""
    stderr = ""


class _Commands:
    def run(self, command, **kwargs):
        assert command
        return _CommandResult()


class _FakeSandbox:
    def __init__(self, sandbox_id="sandbox-test"):
        self.sandbox_id = sandbox_id
        self.commands = _Commands()
        self.paused = False
        self.killed = False

    def pause(self):
        self.paused = True

    def kill(self):
        self.killed = True


class _FakeSandboxClass:
    create_kwargs = None
    last_instance = None

    @classmethod
    def create(cls, **kwargs):
        cls.create_kwargs = kwargs
        cls.last_instance = _FakeSandbox()
        return cls.last_instance

    @classmethod
    def connect(cls, sandbox_id, **kwargs):
        cls.last_instance = _FakeSandbox(sandbox_id)
        return cls.last_instance

    @classmethod
    def kill(cls, sandbox_id, **kwargs):
        return bool(sandbox_id)


@pytest.mark.asyncio
async def test_e2b_missing_key_is_unavailable():
    provider = E2BSandboxProvider(Settings(_env_file=None, e2b_api_key=""))
    info = await provider.create("conversation")
    assert info.status.value == "unavailable"
    assert "WORKSPACE_UNAVAILABLE" in (info.message or "")


@pytest.mark.asyncio
async def test_e2b_current_sdk_create_pause_resume_and_destroy(monkeypatch):
    settings = Settings(
        _env_file=None,
        e2b_api_key="example-sandbox-key",
        e2b_timeout_sec=3600,
    )
    provider = E2BSandboxProvider(settings)
    monkeypatch.setattr(provider, "_get_sandbox_class", lambda: _FakeSandboxClass)

    created = await provider.create("conversation")
    assert created.status.value == "running"
    assert _FakeSandboxClass.create_kwargs == {
        "api_key": "example-sandbox-key",
        "timeout": 3600,
    }

    first = _FakeSandboxClass.last_instance
    stopped = await provider.stop("conversation", created.sandbox_id)
    assert stopped.status.value == "stopped"
    assert first.paused is True

    resumed = await provider.start("conversation", created.sandbox_id)
    assert resumed.status.value == "running"
    second = _FakeSandboxClass.last_instance
    await provider.destroy("conversation", created.sandbox_id)
    assert second.killed is True
