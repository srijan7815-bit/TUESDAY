"""Typed JSON-schema tools resolved against the active conversation workspace."""

from __future__ import annotations

import base64
import json
import re
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.approval_gate import consume_or_request_approval
from app.core.command_policy import authorize_remote_command
from app.core.config import get_settings
from app.core.logging import get_logger
from app.sandbox.manager import WorkspaceManager
from app.sandbox.provider import ProviderError, WORKSPACE_UNAVAILABLE

log = get_logger(__name__)

# OpenAI-compatible tool schemas
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "computer_list_dir",
            "description": "List files in a directory under /workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute workspace path, e.g. /workspace",
                        "default": "/workspace",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_read_file",
            "description": "Read a UTF-8 text file from the workspace (bounded size).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path under /workspace",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_write_file",
            "description": "Write text content to a file under /workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_mkdir",
            "description": "Create a directory under /workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_move_file",
            "description": "Move or rename a file/directory within /workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string"},
                    "dst": {"type": "string"},
                },
                "required": ["src", "dst"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_delete_file",
            "description": "Delete a file or directory under /workspace (not the root).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_run_command",
            "description": "Run a shell command inside the conversation workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {
                        "type": "string",
                        "description": "Working directory under /workspace",
                    },
                    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 120},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_screenshot",
            "description": "Capture the workspace desktop/screenshot as PNG (base64).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_get_screen_size",
            "description": "Return the current remote desktop dimensions.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_click",
            "description": "Click a point in the remote desktop after user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "minimum": 0},
                    "y": {"type": "integer", "minimum": 0},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_double_click",
            "description": "Double-click a point in the remote desktop after user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "minimum": 0},
                    "y": {"type": "integer", "minimum": 0},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_scroll",
            "description": "Scroll the remote desktop (positive up, negative down) after user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "integer", "minimum": -100, "maximum": 100}
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_type",
            "description": "Type text into the focused remote application after user approval.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "maxLength": 8000}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_keypress",
            "description": "Press one key or a key combination in the remote desktop after user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 5,
                            },
                        ]
                    }
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_export_artifact",
            "description": "Copy a workspace file into /workspace/artifacts for user download.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Source path under /workspace",
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional artifact filename",
                    },
                },
                "required": ["path"],
            },
        },
    },
]


class ToolExecutor:
    """Executes tool calls server-side with conversation-scoped workspace resolution."""

    def __init__(self, manager: WorkspaceManager) -> None:
        self.manager = manager

    async def execute(
        self,
        session: AsyncSession,
        conversation_id: str,
        name: str,
        arguments: dict[str, Any] | str | None,
    ) -> dict[str, Any]:
        args = self._parse_args(arguments)
        try:
            return await self._dispatch(session, conversation_id, name, args)
        except ProviderError as exc:
            return {
                "ok": False,
                "error_code": exc.code,
                "error": exc.message,
                "unavailable": exc.code == WORKSPACE_UNAVAILABLE
                or WORKSPACE_UNAVAILABLE in exc.message,
            }
        except Exception:
            log.exception("tool %s failed", name)
            return {
                "ok": False,
                "error_code": "TOOL_ERROR",
                "error": "Tool execution failed; check server logs",
            }

    @staticmethod
    def _parse_args(arguments: dict[str, Any] | str | None) -> dict[str, Any]:
        if arguments is None:
            return {}
        if isinstance(arguments, dict):
            return arguments
        if isinstance(arguments, str):
            if not arguments.strip():
                return {}
            try:
                data = json.loads(arguments)
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {"_raw": arguments}
        return {}

    async def _dispatch(
        self,
        session: AsyncSession,
        conversation_id: str,
        name: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        if name == "computer_list_dir":
            path = str(args.get("path") or "/workspace")
            entries = await self.manager.list_dir(session, conversation_id, path)
            return {"ok": True, "path": path, "entries": entries}

        if name == "computer_read_file":
            path = str(args["path"])
            data = await self.manager.read_file(session, conversation_id, path)
            # Prefer text; fall back to base64
            try:
                text = data.decode("utf-8")
                return {"ok": True, "path": path, "content": text, "encoding": "utf-8"}
            except UnicodeDecodeError:
                b64 = base64.b64encode(data).decode("ascii")
                return {
                    "ok": True,
                    "path": path,
                    "content_base64": b64,
                    "encoding": "base64",
                    "size": len(data),
                }

        if name == "computer_write_file":
            path = str(args["path"])
            content = str(args.get("content") or "")
            await self.manager.write_file(
                session, conversation_id, path, content.encode("utf-8")
            )
            return {"ok": True, "path": path, "bytes": len(content.encode("utf-8"))}

        if name == "computer_mkdir":
            path = str(args["path"])
            await self.manager.mkdir(session, conversation_id, path)
            return {"ok": True, "path": path}

        if name == "computer_move_file":
            src, dst = str(args["src"]), str(args["dst"])
            await self.manager.move_file(session, conversation_id, src, dst)
            return {"ok": True, "src": src, "dst": dst}

        if name == "computer_delete_file":
            path = str(args["path"])
            if get_settings().require_approval_for_destructive:
                pending = await consume_or_request_approval(
                    session,
                    conversation_id=conversation_id,
                    action="workspace.delete",
                    summary=f"Delete {path} from the remote workspace",
                    details={"path": path},
                )
                if pending:
                    return pending
            await self.manager.delete_path(session, conversation_id, path)
            return {"ok": True, "path": path, "deleted": True}

        if name == "computer_run_command":
            command = str(args["command"])
            cwd = args.get("cwd")
            timeout = args.get("timeout_sec")
            pending = await authorize_remote_command(
                session,
                conversation_id=conversation_id,
                command=command,
                cwd=str(cwd) if cwd else None,
            )
            if pending:
                return pending
            result = await self.manager.execute(
                session,
                conversation_id,
                command,
                cwd=str(cwd) if cwd else None,
                timeout_sec=int(timeout) if timeout else None,
            )
            return {"ok": True, **result}

        if name == "computer_screenshot":
            shot = await self.manager.screenshot(session, conversation_id)
            b64 = base64.b64encode(shot.data).decode("ascii")
            # Bound tool result size in text form
            preview = b64[:8000]
            return {
                "ok": True,
                "content_type": shot.content_type,
                "width": shot.width,
                "height": shot.height,
                "data_base64_preview": preview,
                "data_base64_truncated": len(b64) > len(preview),
                "byte_length": len(shot.data),
                "note": "Full image available via GET /v1/conversations/{id}/workspace/screenshot",
            }

        if name == "computer_get_screen_size":
            shot = await self.manager.screenshot(session, conversation_id)
            return {"ok": True, "width": shot.width, "height": shot.height}

        if name in {
            "computer_click",
            "computer_double_click",
            "computer_scroll",
            "computer_type",
            "computer_keypress",
        }:
            details = {
                k: v
                for k, v in args.items()
                if k in {"x", "y", "amount", "text", "keys"}
            }
            if get_settings().require_approval_for_gui:
                pending = await consume_or_request_approval(
                    session,
                    conversation_id=conversation_id,
                    action="workspace.gui",
                    summary=f"Allow remote desktop input: {name.removeprefix('computer_')}",
                    details={"tool": name, **details},
                )
                if pending:
                    return pending
            if name == "computer_click":
                await self.manager.click(
                    session, conversation_id, int(args["x"]), int(args["y"])
                )
            elif name == "computer_double_click":
                await self.manager.click(
                    session,
                    conversation_id,
                    int(args["x"]),
                    int(args["y"]),
                    double=True,
                )
            elif name == "computer_scroll":
                await self.manager.scroll(session, conversation_id, int(args["amount"]))
            elif name == "computer_type":
                await self.manager.type_text(
                    session, conversation_id, str(args["text"])[:8000]
                )
            else:
                keys = args["keys"]
                if not isinstance(keys, (str, list)):
                    return {
                        "ok": False,
                        "error_code": "INVALID_ARGUMENT",
                        "error": "keys must be a string or list",
                    }
                await self.manager.keypress(session, conversation_id, keys)
            return {"ok": True, "action": name.removeprefix("computer_")}

        if name == "computer_export_artifact":
            path = str(args["path"])
            name_opt = args.get("name")
            data = await self.manager.read_file(session, conversation_id, path)
            base = PurePosixPath(str(name_opt) if name_opt else path).name
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", base):
                return {
                    "ok": False,
                    "error_code": "INVALID_ARTIFACT_NAME",
                    "error": "Artifact name must be a safe filename",
                }
            dest = f"/workspace/artifacts/{base}"
            await self.manager.write_file(session, conversation_id, dest, data)
            return {"ok": True, "artifact_path": dest, "bytes": len(data)}

        return {
            "ok": False,
            "error_code": "UNKNOWN_TOOL",
            "error": f"Unknown tool: {name}",
        }
