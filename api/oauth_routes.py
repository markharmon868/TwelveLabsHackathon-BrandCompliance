"""
Frame.io v4 OAuth 2.0 flow (Adobe IMS).

Endpoints:
  GET /oauth/login     — redirect the browser to Adobe's authorization page
  GET /oauth/callback  — receive the auth code, exchange for tokens, persist to .env
"""

import os
import secrets
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

load_dotenv()

router = APIRouter(prefix="/oauth", tags=["oauth"])

# Adobe IMS endpoints
_IMS_AUTH_URL = "https://ims-na1.adobelogin.com/ims/authorize/v2"
_IMS_TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"

# Read env vars at request time via helpers so restarts aren't needed after .env edits
def _client_id() -> str:
    return os.getenv("FRAMEIO_CLIENT_ID", "").strip()

def _client_secret() -> str:
    return os.getenv("FRAMEIO_CLIENT_SECRET", "").strip()

def _redirect_uri() -> str:
    return os.getenv("FRAMEIO_REDIRECT_URI", "").strip()

def _scope() -> str:
    return os.getenv("FRAMEIO_OAUTH_SCOPE", "openid,profile,email,offline_access,additional_info.roles")

# Simple in-memory CSRF state store (fine for a single-user hackathon tool)
_pending_states: set[str] = set()

# Locate the .env file at the project root (two levels up from this file)
_ENV_FILE = Path(__file__).parent.parent / ".env"


def _write_env_tokens(access_token: str, refresh_token: str | None) -> None:
    """
    Upsert FRAMEIO_API_TOKEN (and optionally FRAMEIO_REFRESH_TOKEN) in the .env file,
    then reload them into os.environ so the running process picks them up immediately.
    """
    lines: list[str] = []
    if _ENV_FILE.exists():
        lines = _ENV_FILE.read_text().splitlines()

    def _upsert(key: str, value: str) -> None:
        for i, line in enumerate(lines):
            if line.startswith(f"{key} =") or line.startswith(f"{key}="):
                lines[i] = f"{key} = {value}"
                return
        lines.append(f"{key} = {value}")

    _upsert("FRAMEIO_API_TOKEN", access_token)
    if refresh_token:
        _upsert("FRAMEIO_REFRESH_TOKEN", refresh_token)

    _ENV_FILE.write_text("\n".join(lines) + "\n")

    # Reload into the current process
    os.environ["FRAMEIO_API_TOKEN"] = access_token
    if refresh_token:
        os.environ["FRAMEIO_REFRESH_TOKEN"] = refresh_token

    # Patch the frameio module's in-memory token so ongoing requests use the new token
    try:
        from . import frameio as _frameio
        _frameio.FRAMEIO_TOKEN = access_token
    except Exception:
        pass


@router.get("/login")
def oauth_login() -> RedirectResponse:
    """
    Redirect the user's browser to the Adobe IMS authorization page.
    Requires FRAMEIO_CLIENT_ID and FRAMEIO_REDIRECT_URI to be set in .env.
    """
    if not _client_id() or not _redirect_uri():
        raise HTTPException(
            status_code=500,
            detail="FRAMEIO_CLIENT_ID and FRAMEIO_REDIRECT_URI must be set in .env",
        )

    state = secrets.token_urlsafe(16)
    _pending_states.add(state)

    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "scope": _scope(),
        "response_type": "code",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{_IMS_AUTH_URL}?{query}")


@router.get("/callback")
def oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> HTMLResponse:
    """
    Adobe IMS redirects here after the user authorises the app.
    Exchanges the code for access + refresh tokens and writes them to .env.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Adobe OAuth error: {error} — {error_description}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    if state not in _pending_states:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")
    _pending_states.discard(state)

    if not _client_id() or not _client_secret() or not _redirect_uri():
        raise HTTPException(
            status_code=500,
            detail="FRAMEIO_CLIENT_ID, FRAMEIO_CLIENT_SECRET, and FRAMEIO_REDIRECT_URI must be set in .env",
        )

    resp = requests.post(
        _IMS_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "redirect_uri": _redirect_uri(),
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )

    if not resp.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Token exchange failed: {resp.status_code} {resp.text}",
        )

    data = resp.json()
    access_token: str = data.get("access_token", "")
    refresh_token: str | None = data.get("refresh_token")

    if not access_token:
        raise HTTPException(
            status_code=502,
            detail=f"No access_token in response: {data}",
        )

    _write_env_tokens(access_token, refresh_token)
    print(f"[OAuth] Tokens stored. access_token length={len(access_token)}")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return RedirectResponse(url=f"{frontend_url}/integrations?connected=1", status_code=302)
