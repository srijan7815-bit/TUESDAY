"""Single-owner authentication for the personal TUESDAY deployment."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import (
    SESSION_COOKIE,
    create_session_cookie,
    request_is_authenticated,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginBody(BaseModel):
    token: str = Field(..., min_length=1, max_length=512)


@router.get("/status")
async def auth_status(request: Request) -> dict[str, bool]:
    settings = get_settings()
    return {
        "auth_required": settings.auth_required,
        "authenticated": request_is_authenticated(request, settings),
    }


@router.post("/session")
async def create_session(body: LoginBody, response: Response) -> dict[str, bool]:
    settings = get_settings()
    if settings.auth_required and not hmac.compare_digest(
        body.token, settings.tuesday_access_token
    ):
        raise HTTPException(status_code=401, detail="Invalid access token")
    response.set_cookie(
        SESSION_COOKIE,
        create_session_cookie(settings),
        max_age=settings.tuesday_session_ttl_sec,
        httponly=True,
        secure=settings.tuesday_env == "production",
        samesite="strict",
        path="/",
    )
    return {"authenticated": True}


@router.delete("/session")
async def delete_session(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"authenticated": False}
