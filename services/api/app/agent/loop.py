"""Iterative plan → tool → observe agent loop with SSE events."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import TOOL_DEFINITIONS, ToolExecutor
from app.core.logging import get_logger
from app.core.model_adapter import ModelAdapter
from app.sandbox.manager import WorkspaceManager

log = get_logger(__name__)

SYSTEM_PROMPT = """You are TUESDAY, a personal agentic AI assistant with a sci-fi HUD interface.
You can use computer_* tools to operate a private remote workspace scoped to this conversation.
Paths must stay under /workspace. Prefer small iterative steps: inspect, act, verify.
If a workspace tool returns WORKSPACE_UNAVAILABLE, continue helping without computer access.
Never invent secrets or claim you used a model/provider that was not actually invoked.
Be concise, precise, and security-conscious. Ask before destructive or network-heavy actions.
"""


class AgentLoop:
    def __init__(
        self,
        model: ModelAdapter | None = None,
        manager: WorkspaceManager | None = None,
        max_tool_rounds: int = 8,
    ) -> None:
        self.model = model or ModelAdapter()
        self.manager = manager or WorkspaceManager()
        self.tools = ToolExecutor(self.manager)
        self.max_tool_rounds = max_tool_rounds

    async def run_stream(
        self,
        session: AsyncSession,
        *,
        conversation_id: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.5,
        max_tokens: int = 2048,
        enable_tools: bool = True,
        task: str = "chat",
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Yields SSE-friendly dict events:
          {event, data}
        """
        history: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *messages,
        ]
        tools = TOOL_DEFINITIONS if enable_tools else None
        used_model: str | None = None

        for round_i in range(self.max_tool_rounds + 1):
            assistant_text: list[str] = []
            tool_calls: list[dict[str, Any]] = []

            async for chunk in self.model.stream_chat(
                history,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                task=task if round_i == 0 else "agent",
            ):
                if chunk.type == "meta":
                    used_model = chunk.model or used_model
                    yield {
                        "event": "meta",
                        "data": {
                            "model": chunk.model,
                            "provider": chunk.content,
                            "conversation_id": conversation_id,
                            "round": round_i,
                        },
                    }
                elif chunk.type == "delta":
                    assistant_text.append(chunk.content)
                    yield {"event": "delta", "data": {"content": chunk.content}}
                elif chunk.type == "tool_calls" and chunk.data:
                    tool_calls = list(chunk.data.get("tool_calls") or [])
                elif chunk.type == "error":
                    yield {
                        "event": "error",
                        "data": {"message": chunk.content, "model": chunk.model},
                    }
                    return
                elif chunk.type == "done":
                    used_model = chunk.model or used_model

            if not tool_calls:
                yield {
                    "event": "done",
                    "data": {
                        "model": used_model,
                        "content": "".join(assistant_text),
                        "conversation_id": conversation_id,
                    },
                }
                return

            # Append assistant message with tool_calls for protocol continuity
            history.append(
                {
                    "role": "assistant",
                    "content": "".join(assistant_text) or None,
                    "tool_calls": tool_calls,
                }
            )

            for tc in tool_calls:
                fn = tc.get("function") or {}
                name = fn.get("name") or ""
                raw_args = fn.get("arguments") or "{}"
                call_id = tc.get("id") or f"call_{round_i}"
                yield {
                    "event": "tool_start",
                    "data": {
                        "id": call_id,
                        "name": name,
                        "arguments": raw_args,
                    },
                }
                result = await self.tools.execute(
                    session, conversation_id, name, raw_args
                )
                # Bound result size for model context
                result_text = json.dumps(result, ensure_ascii=False)
                if len(result_text) > 24_000:
                    result_text = result_text[:24_000] + '…"}'
                yield {
                    "event": "tool_result",
                    "data": {
                        "id": call_id,
                        "name": name,
                        "result": result,
                    },
                }
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": result_text,
                    }
                )

            # If workspace became visible, hint UI
            if any(
                (tc.get("function") or {}).get("name", "").startswith("computer_")
                for tc in tool_calls
            ):
                yield {
                    "event": "workspace",
                    "data": {"active": True, "conversation_id": conversation_id},
                }

        yield {
            "event": "done",
            "data": {
                "model": used_model,
                "content": "",
                "conversation_id": conversation_id,
                "message": "Max tool rounds reached",
            },
        }
