"""Workspace lifecycle and computer-use HTTP routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.approval_gate import consume_or_request_approval
from app.core.command_policy import authorize_remote_command
from app.core.config import get_settings
from app.db.session import get_session
from app.sandbox.manager import get_workspace_manager
from app.sandbox.provider import ProviderError, WORKSPACE_UNAVAILABLE

router = APIRouter(
    prefix="/v1/conversations/{conversation_id}/workspace", tags=["workspace"]
)


class ExecuteBody(BaseModel):
    command: str = Field(..., min_length=1, max_length=8000)
    cwd: str | None = None
    timeout_sec: int | None = Field(default=None, ge=1, le=300)


class WriteBody(BaseModel):
    path: str
    content: str = ""


class MoveBody(BaseModel):
    src: str
    dst: str


class PointBody(BaseModel):
    x: int = Field(..., ge=0, le=16_384)
    y: int = Field(..., ge=0, le=16_384)
    double: bool = False


class ScrollBody(BaseModel):
    amount: int = Field(..., ge=-100, le=100)


class TypeBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)


class KeyBody(BaseModel):
    keys: str | list[str]


def _http_error(exc: ProviderError) -> HTTPException:
    status = (
        503
        if exc.code == WORKSPACE_UNAVAILABLE or WORKSPACE_UNAVAILABLE in exc.message
        else 400
    )
    if exc.code in {"NOT_FOUND"}:
        status = 404
    if exc.code in {"PATH_ESCAPE", "FORBIDDEN", "INVALID_PATH"}:
        status = 400
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": exc.message, **(exc.details or {})},
    )


@router.get("")
async def workspace_status(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    mgr = get_workspace_manager()
    return await mgr.status(session, conversation_id)


@router.post("/start")
async def workspace_start(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    mgr = get_workspace_manager()
    try:
        return await mgr.start(session, conversation_id)
    except ProviderError as exc:
        raise _http_error(exc) from exc


@router.post("/stop")
async def workspace_stop(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    mgr = get_workspace_manager()
    try:
        return await mgr.stop(session, conversation_id)
    except ProviderError as exc:
        raise _http_error(exc) from exc


@router.post("/restart")
async def workspace_restart(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        return await get_workspace_manager().restart(session, conversation_id)
    except ProviderError as exc:
        raise _http_error(exc) from exc


@router.delete("")
async def workspace_destroy(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        if get_settings().require_approval_for_destructive:
            pending = await consume_or_request_approval(
                session,
                conversation_id=conversation_id,
                action="workspace.destroy",
                summary="Permanently delete this conversation's remote workspace",
                details={"conversation_id": conversation_id},
            )
            if pending:
                raise HTTPException(status_code=409, detail=pending)
        await get_workspace_manager().destroy(session, conversation_id)
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return {"ok": True, "conversation_id": conversation_id, "status": "none"}


@router.post("/execute")
async def workspace_execute(
    conversation_id: str,
    body: ExecuteBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    mgr = get_workspace_manager()
    try:
        pending = await authorize_remote_command(
            session,
            conversation_id=conversation_id,
            command=body.command,
            cwd=body.cwd,
        )
        if pending:
            raise HTTPException(status_code=409, detail=pending)
        return await mgr.execute(
            session,
            conversation_id,
            body.command,
            cwd=body.cwd,
            timeout_sec=body.timeout_sec,
        )
    except ProviderError as exc:
        raise _http_error(exc) from exc


@router.get("/screenshot")
async def workspace_screenshot(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    mgr = get_workspace_manager()
    try:
        shot = await mgr.screenshot(session, conversation_id)
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return Response(
        content=shot.data,
        media_type=shot.content_type,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/files")
async def workspace_list_files(
    conversation_id: str,
    path: str = Query(default="/workspace"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    mgr = get_workspace_manager()
    try:
        entries = await mgr.list_dir(session, conversation_id, path)
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return {"path": path, "entries": entries}


@router.get("/files/content")
async def workspace_read_file(
    conversation_id: str,
    path: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    mgr = get_workspace_manager()
    try:
        data = await mgr.read_file(session, conversation_id, path)
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return Response(content=data, media_type="application/octet-stream")


@router.post("/files/write")
async def workspace_write_file(
    conversation_id: str,
    body: WriteBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    mgr = get_workspace_manager()
    try:
        await mgr.write_file(
            session, conversation_id, body.path, body.content.encode("utf-8")
        )
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return {"ok": True, "path": body.path}


@router.post("/files/mkdir")
async def workspace_mkdir(
    conversation_id: str,
    body: WriteBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    mgr = get_workspace_manager()
    try:
        await mgr.mkdir(session, conversation_id, body.path)
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return {"ok": True, "path": body.path}


@router.post("/files/move")
async def workspace_move(
    conversation_id: str,
    body: MoveBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    mgr = get_workspace_manager()
    try:
        await mgr.move_file(session, conversation_id, body.src, body.dst)
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return {"ok": True, "src": body.src, "dst": body.dst}


@router.delete("/files")
async def workspace_delete(
    conversation_id: str,
    path: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    mgr = get_workspace_manager()
    try:
        if get_settings().require_approval_for_destructive:
            pending = await consume_or_request_approval(
                session,
                conversation_id=conversation_id,
                action="workspace.delete",
                summary=f"Delete {path} from the remote workspace",
                details={"path": path},
            )
            if pending:
                raise HTTPException(status_code=409, detail=pending)
        await mgr.delete_path(session, conversation_id, path)
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return {"ok": True, "path": path, "deleted": True}


async def _gui_approval(
    session: AsyncSession, conversation_id: str, tool: str, details: dict[str, Any]
) -> None:
    if not get_settings().require_approval_for_gui:
        return
    pending = await consume_or_request_approval(
        session,
        conversation_id=conversation_id,
        action="workspace.gui",
        summary=f"Allow remote desktop input: {tool}",
        details={"tool": tool, **details},
    )
    if pending:
        raise HTTPException(status_code=409, detail=pending)


@router.post("/input/click")
async def workspace_click(
    conversation_id: str,
    body: PointBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    details = {"x": body.x, "y": body.y}
    tool = "computer_double_click" if body.double else "computer_click"
    await _gui_approval(session, conversation_id, tool, details)
    try:
        await get_workspace_manager().click(
            session, conversation_id, body.x, body.y, double=body.double
        )
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return {"ok": True}


@router.post("/input/scroll")
async def workspace_scroll(
    conversation_id: str,
    body: ScrollBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _gui_approval(
        session, conversation_id, "computer_scroll", {"amount": body.amount}
    )
    try:
        await get_workspace_manager().scroll(session, conversation_id, body.amount)
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return {"ok": True}


@router.post("/input/type")
async def workspace_type(
    conversation_id: str,
    body: TypeBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _gui_approval(session, conversation_id, "computer_type", {"text": body.text})
    try:
        await get_workspace_manager().type_text(session, conversation_id, body.text)
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return {"ok": True}


@router.post("/input/keypress")
async def workspace_keypress(
    conversation_id: str,
    body: KeyBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if isinstance(body.keys, list) and (not body.keys or len(body.keys) > 5):
        raise HTTPException(status_code=422, detail="keys must contain 1 to 5 entries")
    await _gui_approval(
        session, conversation_id, "computer_keypress", {"keys": body.keys}
    )
    try:
        await get_workspace_manager().keypress(session, conversation_id, body.keys)
    except ProviderError as exc:
        raise _http_error(exc) from exc
    return {"ok": True}
