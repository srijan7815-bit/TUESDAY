"""OpenAI-compatible model adapter for NVIDIA + development mock."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class StreamChunk:
    type: str  # delta | tool_calls | done | error | meta
    content: str = ""
    data: dict[str, Any] | None = None
    model: str | None = None


class ModelAdapter:
    """Streams chat completions from NVIDIA or a local mock."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def select_model(self, requested: str | None, *, task: str = "chat") -> str:
        if requested:
            return requested
        if task in {"code", "planning", "agent"}:
            return self.settings.nvidia_model_primary
        return self.settings.nvidia_model_fast or self.settings.nvidia_model_primary

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.6,
        max_tokens: int = 2048,
        tools: list[dict[str, Any]] | None = None,
        task: str = "chat",
    ) -> AsyncIterator[StreamChunk]:
        chosen = self.select_model(model, task=task)
        if not self.settings.has_nvidia:
            if not self.settings.tuesday_allow_mock_model:
                yield StreamChunk(
                    type="error",
                    content="NVIDIA_API_KEY is not configured and mock model is disabled.",
                )
                return
            async for chunk in self._mock_stream(messages, model=chosen, tools=tools):
                yield chunk
            return

        async for chunk in self._nvidia_stream(
            messages,
            model=chosen,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        ):
            yield chunk

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 2048,
        tools: list[dict[str, Any]] | None = None,
        task: str = "chat",
    ) -> dict[str, Any]:
        """Non-streaming completion; aggregates stream."""
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        used_model: str | None = None
        async for chunk in self.stream_chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            task=task,
        ):
            if chunk.type == "delta":
                text_parts.append(chunk.content)
            elif chunk.type == "tool_calls" and chunk.data:
                tool_calls.extend(chunk.data.get("tool_calls") or [])
            elif chunk.type == "error":
                return {"error": chunk.content, "model": chunk.model}
            elif chunk.type == "meta":
                used_model = chunk.model or used_model
            elif chunk.type == "done":
                used_model = chunk.model or used_model
        return {
            "content": "".join(text_parts),
            "tool_calls": tool_calls,
            "model": used_model,
        }

    async def _nvidia_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
    ) -> AsyncIterator[StreamChunk]:
        url = self.settings.nvidia_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.nvidia_api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        yield StreamChunk(type="meta", model=model, content="nvidia")

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=30.0)
            ) as client:
                async with client.stream(
                    "POST", url, headers=headers, json=body
                ) as resp:
                    if resp.status_code >= 400:
                        err_body = (await resp.aread()).decode(
                            "utf-8", errors="replace"
                        )[:500]
                        # fallback attempt with fast model once
                        if (
                            model != self.settings.nvidia_model_fast
                            and self.settings.nvidia_model_fast
                        ):
                            log.warning(
                                "Primary model failed status=%s; trying fast model",
                                resp.status_code,
                            )
                            async for c in self._nvidia_stream(
                                messages,
                                model=self.settings.nvidia_model_fast,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                tools=tools,
                            ):
                                yield c
                            return
                        yield StreamChunk(
                            type="error",
                            content=f"Model provider error HTTP {resp.status_code}: {err_body}",
                            model=model,
                        )
                        return

                    tool_acc: dict[int, dict[str, Any]] = {}
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith(":"):
                            continue
                        if not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            data = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        if delta.get("content"):
                            yield StreamChunk(
                                type="delta", content=delta["content"], model=model
                            )
                        for tc in delta.get("tool_calls") or []:
                            idx = int(tc.get("index", 0))
                            slot = tool_acc.setdefault(
                                idx,
                                {
                                    "id": tc.get("id") or f"call_{idx}",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                },
                            )
                            if tc.get("id"):
                                slot["id"] = tc["id"]
                            fn = tc.get("function") or {}
                            if fn.get("name"):
                                slot["function"]["name"] += fn["name"]
                            if fn.get("arguments"):
                                slot["function"]["arguments"] += fn["arguments"]
                    if tool_acc:
                        ordered = [tool_acc[i] for i in sorted(tool_acc)]
                        yield StreamChunk(
                            type="tool_calls",
                            data={"tool_calls": ordered},
                            model=model,
                        )
                    yield StreamChunk(type="done", model=model)
        except httpx.HTTPError as exc:
            log.exception("NVIDIA stream failed")
            yield StreamChunk(
                type="error", content=f"Model transport error: {exc}", model=model
            )

    async def _mock_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        tools: list[dict[str, Any]] | None,
    ) -> AsyncIterator[StreamChunk]:
        """Deterministic development stream — never claims to be Nemotron."""
        yield StreamChunk(type="meta", model=f"mock:{model}", content="mock")
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = str(m.get("content") or "")
                break

        # Simple tool-call simulation for agent tests — only on the first round
        # (no prior tool results yet), so the loop can complete.
        has_tool_results = any(m.get("role") == "tool" for m in messages)
        lower = last_user.lower()
        wants_list = (
            "list workspace" in lower
            or "list the workspace" in lower
            or lower.strip() == "/tools demo"
        )
        if tools and wants_list and not has_tool_results:
            call = {
                "id": "call_mock_list",
                "type": "function",
                "function": {
                    "name": "computer_list_dir",
                    "arguments": json.dumps({"path": "/workspace"}),
                },
            }
            yield StreamChunk(
                type="tool_calls", data={"tool_calls": [call]}, model=f"mock:{model}"
            )
            yield StreamChunk(type="done", model=f"mock:{model}")
            return

        if has_tool_results and wants_list:
            # Summarize tool output after the mock tool round
            tool_bits = []
            for m in messages:
                if m.get("role") == "tool":
                    tool_bits.append(str(m.get("content") or "")[:400])
            reply = (
                "Workspace listing complete (mock model). "
                f"Tool output preview: {tool_bits[-1] if tool_bits else '(none)'}. "
                "Configure NVIDIA_API_KEY for full Nemotron agent reasoning."
            )
        else:
            reply = (
                "TUESDAY online. Mock model is active because NVIDIA_API_KEY is not configured. "
                f"I received your message ({len(last_user)} chars). "
                "Configure NVIDIA_API_KEY for Nemotron routing. "
                "Workspace tools remain available via the local sandbox provider."
            )
        # stream in small pieces
        words = reply.split(" ")
        buf: list[str] = []
        for i, w in enumerate(words):
            buf.append(w)
            if len(buf) >= 4 or i == len(words) - 1:
                piece = (" ".join(buf)) + (" " if i < len(words) - 1 else "")
                yield StreamChunk(type="delta", content=piece, model=f"mock:{model}")
                buf.clear()
                # tiny yield point
                await asyncio.sleep(0)
        yield StreamChunk(type="done", model=f"mock:{model}")
