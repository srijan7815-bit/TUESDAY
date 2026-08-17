import pytest

from app.sandbox.paths import (
    is_blocked_network_target,
    map_to_host,
    normalize_workspace_path,
)
from app.core.command_policy import command_network_targets, command_uses_network
from app.sandbox.provider import ProviderError


def test_normalize_relative():
    assert normalize_workspace_path("projects/foo") == "/workspace/projects/foo"


def test_normalize_absolute_ok():
    assert normalize_workspace_path("/workspace/a/b") == "/workspace/a/b"


def test_normalize_traversal_rejected():
    with pytest.raises(ProviderError) as ei:
        normalize_workspace_path("/workspace/../etc/passwd")
    assert ei.value.code == "PATH_ESCAPE"


def test_normalize_host_absolute_rejected():
    with pytest.raises(ProviderError):
        normalize_workspace_path("/etc/passwd")


def test_normalize_dotdot_inside():
    assert normalize_workspace_path("/workspace/a/../b") == "/workspace/b"


def test_map_to_host(tmp_path):
    p = map_to_host("/workspace/uploads/x.txt", tmp_path)
    assert p == (tmp_path / "uploads" / "x.txt").resolve()


def test_map_escape(tmp_path):
    with pytest.raises(ProviderError):
        map_to_host("/workspace/../../etc/passwd", tmp_path)


@pytest.mark.parametrize(
    "host,blocked",
    [
        ("localhost", True),
        ("127.0.0.1", True),
        ("10.0.0.5", True),
        ("192.168.1.1", True),
        ("172.16.0.1", True),
        ("169.254.169.254", True),
        ("::1", True),
        ("service.internal", True),
        ("example.com", False),
        ("8.8.8.8", False),
    ],
)
def test_network_policy(host, blocked):
    assert is_blocked_network_target(host) is blocked


def test_command_network_detection():
    assert command_network_targets("curl https://example.com/file") == {"example.com"}
    assert command_network_targets("wget http://169.254.169.254/latest") == {
        "169.254.169.254"
    }
    assert command_uses_network("git clone git@github.com:owner/repo.git")
    assert not command_uses_network("python3 -m pytest")
