"""
Frame.io integration API routes.

Endpoints:
  GET  /frameio/status              — check connection (token validity + /me)
  GET  /frameio/config              — get stored webhook/guidelines config
  PUT  /frameio/config              — update config (default_guidelines, workspace, etc.)
  GET  /frameio/workspaces          — list accessible workspaces
  POST /frameio/webhook/register    — register webhook for a workspace
  POST /frameio/audit               — manually trigger audit from a Frame.io asset ID
"""

import json

from fastapi import APIRouter, Body, HTTPException

from brand_compliance import Guidelines
from . import frameio as _fio
from .frameio import (
    download_asset,
    get_asset,
    get_workspaces,
    is_video_asset,
    register_custom_action,
    register_webhook,
)
from .frameio_config import load_config, save_config
from .jobs import GUIDELINES_DIR, VIDEOS_DIR, create_job

router = APIRouter(prefix="/frameio", tags=["frameio"])


# ---------------------------------------------------------------------------
# Connection status
# ---------------------------------------------------------------------------

@router.get("/status")
def frameio_status() -> dict:
    """
    Returns whether a valid Frame.io token is configured.
    Makes a live /me call to verify the token works.
    """
    if not _fio.FRAMEIO_TOKEN:
        return {"connected": False, "user": None}
    try:
        me = _fio.get_me()
        user = me.get("data", me)
        return {
            "connected": True,
            "user": {
                "name": user.get("name") or user.get("display_name") or user.get("email"),
                "email": user.get("email"),
                "account_id": user.get("account_id"),
            },
        }
    except Exception as e:
        return {"connected": False, "user": None, "error": str(e)}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@router.get("/config")
def get_frameio_config() -> dict:
    return load_config()


@router.put("/config")
def update_frameio_config(data: dict = Body(...)) -> dict:
    return save_config(data)


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------

@router.get("/workspaces")
def list_frameio_workspaces() -> dict:
    try:
        workspaces = get_workspaces()
        return {"workspaces": workspaces}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Frame.io error: {e}")


# ---------------------------------------------------------------------------
# Webhook registration
# ---------------------------------------------------------------------------

@router.post("/custom-action/register")
def register_frameio_custom_action(data: dict = Body(...)) -> dict:
    """Register the 'Submit for Compliance Review' Custom Action on the account."""
    action_url = (data.get("action_url") or "").strip()
    if not action_url:
        raise HTTPException(status_code=422, detail="action_url is required")

    try:
        account_id = _fio._get_account_id()
        result = register_custom_action(
            account_id=account_id,
            name="Submit for Compliance Review",
            description="Run a brand compliance audit via The Obsidian Lens",
            url=action_url,
        )
        action_data = result.get("data", result)
        action_id = action_data.get("id", "")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to register custom action: {e}")

    save_config({"custom_action_id": action_id, "custom_action_url": action_url})
    return {"custom_action_id": action_id, "status": "registered"}


@router.post("/webhook/register")
def register_frameio_webhook(data: dict = Body(...)) -> dict:
    """Register a webhook for a workspace and persist to config."""
    workspace_id = (data.get("workspace_id") or "").strip()
    webhook_url = (data.get("webhook_url") or "").strip()

    if not workspace_id or not webhook_url:
        raise HTTPException(
            status_code=422,
            detail="workspace_id and webhook_url are required",
        )

    try:
        result = register_webhook(workspace_id, webhook_url)
        webhook_data = result.get("data", result)
        webhook_id = webhook_data.get("id", "")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to register webhook: {e}")

    save_config(
        {
            "workspace_id": workspace_id,
            "webhook_id": webhook_id,
            "webhook_url": webhook_url,
        }
    )
    return {"webhook_id": webhook_id, "status": "registered"}


# ---------------------------------------------------------------------------
# Manual audit trigger
# ---------------------------------------------------------------------------

@router.post("/audit")
def trigger_frameio_audit(data: dict = Body(...)) -> dict:
    """
    Manually kick off a compliance audit for a Frame.io asset.
    Returns the created job_id so the frontend can redirect to the job page.
    """
    asset_id = (data.get("asset_id") or "").strip()
    guidelines_filename = (data.get("guidelines_filename") or "").strip()

    if not asset_id:
        raise HTTPException(status_code=422, detail="asset_id is required")

    # Resolve guidelines file
    if guidelines_filename:
        guidelines_path = GUIDELINES_DIR / guidelines_filename
    else:
        cfg = load_config()
        default = cfg.get("default_guidelines", "")
        guidelines_path = GUIDELINES_DIR / default if default else None

    if not guidelines_path or not guidelines_path.exists():
        available = sorted(GUIDELINES_DIR.glob("*.json"))
        if not available:
            raise HTTPException(status_code=422, detail="No guidelines files found.")
        guidelines_path = available[0]

    with guidelines_path.open() as f:
        guidelines = Guidelines.from_dict(json.load(f))

    # Fetch asset metadata from Frame.io
    try:
        asset = get_asset(asset_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch asset: {e}")

    if not is_video_asset(asset):
        raise HTTPException(status_code=422, detail="Asset is not a video file.")

    # Download video
    try:
        VIDEOS_DIR.mkdir(exist_ok=True)
        video_path = download_asset(asset, VIDEOS_DIR)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to download asset: {e}")

    job_id = create_job(
        video_path=video_path,
        guidelines=guidelines,
        video_filename=asset.get("name", video_path.name),
        guidelines_filename=guidelines_path.name,
        frame_io_asset_id=asset_id,
        source="custom_action",
    )

    return {"job_id": job_id, "asset_id": asset_id}
