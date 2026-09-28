"""
Short-lived download tokens.

POST /api/auth/download-token   (auth required)
    body:     {"path": "/api/..."}
    response: {"token": "<exp>.<hexsig>", "expires_in": 120}

The returned token is appended to a download URL as ``?dl=<token>`` and is
accepted by ``verify_token`` only for the exact signed path, for GET/HEAD,
until it expires. This replaces embedding the long-lived bearer token in
browser-opened download links.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.core import auth as _auth
from backend.core.auth import verify_token

router = APIRouter(tags=["auth"])

_MAX_PATH_LEN = 2048


class DownloadTokenRequest(BaseModel):
    path: str = Field(..., max_length=_MAX_PATH_LEN)


class DownloadTokenResponse(BaseModel):
    token: str
    expires_in: int


@router.post(
    "/api/auth/download-token",
    response_model=DownloadTokenResponse,
    dependencies=[Depends(verify_token)],
)
async def create_download_token(body: DownloadTokenRequest) -> DownloadTokenResponse:
    """Mint a path-scoped download token valid for DOWNLOAD_TOKEN_TTL seconds."""
    path = body.path.split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/api/"):
        raise HTTPException(status_code=400, detail="path must start with /api/")
    return DownloadTokenResponse(
        token=_auth.issue_download_token(path),
        expires_in=_auth.DOWNLOAD_TOKEN_TTL,
    )
