"""Attachment staging, speech recognition, speech synthesis, and artifact downloads."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_session
from app.sandbox.manager import get_workspace_manager
from app.sandbox.provider import ProviderError

router = APIRouter(prefix="/v1/media", tags=["media"])
log = get_logger(__name__)

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_ALLOWED_UPLOAD_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "audio/wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/webm",
    "audio/ogg",
    "text/plain",
    "text/markdown",
    "application/json",
    "application/pdf",
    "application/zip",
}


def _safe_filename(value: str | None) -> str:
    name = PurePosixPath((value or "attachment.bin").replace("\\", "/")).name
    cleaned = _SAFE_NAME.sub("_", name).strip("._")[:120]
    return cleaned or "attachment.bin"


def _provider_error(exc: ProviderError) -> HTTPException:
    return HTTPException(
        status_code=503, detail={"code": exc.code, "message": exc.message}
    )


@router.post("/attachments")
async def upload_attachment(
    conversation_id: str = Form(..., min_length=1, max_length=80),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    settings = get_settings()
    content_type = (file.content_type or "application/octet-stream").lower()
    if content_type not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=415, detail=f"Unsupported attachment type: {content_type}"
        )
    data = await file.read(settings.sandbox_max_file_bytes + 1)
    await file.close()
    if len(data) > settings.sandbox_max_file_bytes:
        raise HTTPException(
            status_code=413, detail="Attachment exceeds configured limit"
        )
    filename = _safe_filename(file.filename)
    path = f"/workspace/uploads/{filename}"
    manager = get_workspace_manager()
    try:
        await manager.start(session, conversation_id)
        await manager.write_file(session, conversation_id, path, data)
    except ProviderError as exc:
        raise _provider_error(exc) from exc
    return {
        "ok": True,
        "path": path,
        "filename": filename,
        "size": len(data),
        "content_type": content_type,
    }


@router.get("/artifacts/{conversation_id}/{filename}")
async def download_artifact(
    conversation_id: str,
    filename: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    safe_name = _safe_filename(filename)
    try:
        data = await get_workspace_manager().read_file(
            session, conversation_id, f"/workspace/artifacts/{safe_name}"
        )
    except ProviderError as exc:
        raise _provider_error(exc) from exc
    return Response(
        data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)) -> dict[str, Any]:
    settings = get_settings()
    if settings.stt_provider == "none" or not settings.stt_api_url:
        raise HTTPException(
            status_code=503, detail="Speech recognition is not configured"
        )
    if not settings.has_nvidia:
        raise HTTPException(
            status_code=503, detail="NVIDIA speech credentials are not configured"
        )
    audio = await file.read(settings.stt_max_audio_bytes + 1)
    await file.close()
    if len(audio) > settings.stt_max_audio_bytes:
        raise HTTPException(status_code=413, detail="Audio exceeds configured limit")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=20)) as client:
            result = await client.post(
                settings.stt_api_url,
                headers={"Authorization": f"Bearer {settings.nvidia_api_key}"},
                data={"model": settings.stt_model, "response_format": "json"},
                files={
                    "file": (
                        _safe_filename(file.filename),
                        audio,
                        file.content_type or "audio/webm",
                    )
                },
            )
            result.raise_for_status()
            payload = result.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("STT provider request failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="Speech recognition provider failed"
        ) from exc
    text = payload.get("text") or payload.get("transcript")
    if not isinstance(text, str):
        raise HTTPException(
            status_code=502, detail="Speech provider returned no transcript"
        )
    return {
        "text": text,
        "provider": settings.stt_provider,
        "model": settings.stt_model,
    }


class SpeechBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    format: str = Field(default="mp3", pattern="^(mp3|wav|opus)$")


@router.post("/speak")
async def synthesize_speech(body: SpeechBody) -> Response:
    settings = get_settings()
    if settings.tts_provider != "fish" or not settings.fish_audio_api_key:
        raise HTTPException(
            status_code=503, detail="Speech synthesis is not configured"
        )
    payload: dict[str, Any] = {
        "text": body.text,
        "format": body.format,
        "normalize": True,
        "latency": "balanced",
        "prosody": {"speed": 1, "volume": 0, "normalize_loudness": True},
    }
    if settings.fish_audio_voice_id:
        payload["reference_id"] = settings.fish_audio_voice_id
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=20)) as client:
            result = await client.post(
                settings.fish_audio_api_url,
                headers={
                    "Authorization": f"Bearer {settings.fish_audio_api_key}",
                    "Content-Type": "application/json",
                    "model": settings.fish_audio_model,
                },
                json=payload,
            )
            result.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("TTS provider request failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="Speech synthesis provider failed"
        ) from exc
    media_type = {"mp3": "audio/mpeg", "wav": "audio/wav", "opus": "audio/ogg"}[
        body.format
    ]
    return Response(
        result.content, media_type=media_type, headers={"Cache-Control": "no-store"}
    )
