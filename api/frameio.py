"""
Frame.io v4 API client.

Handles asset fetching, video downloading, and posting compliance
violations back as timestamped comments on the asset.
"""

import hashlib
import hmac
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

FRAMEIO_API_BASE = "https://api.frame.io/v4"
FRAMEIO_TOKEN = os.getenv("FRAMEIO_API_TOKEN", "").strip()
_account_id_cache: str = os.getenv("FRAMEIO_ACCOUNT_ID", "").strip()

# Default frame rate used when converting seconds → HH:MM:SS:FF timestamps.
DEFAULT_FPS = 24


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {FRAMEIO_TOKEN}",
        "Content-Type": "application/json",
    }


def _get_account_id() -> str:
    """Return account_id from env or by fetching /v4/me."""
    global _account_id_cache
    if _account_id_cache:
        return _account_id_cache
    me = get_me()
    # v4 /me wraps the user in a "data" key
    user = me.get("data", me)
    _account_id_cache = user["account_id"]
    return _account_id_cache


def _seconds_to_timestamp(seconds: float, fps: float = DEFAULT_FPS) -> str:
    """Convert seconds to HH:MM:SS:FF format required by Frame.io v4 comments."""
    total_frames = int(seconds * fps)
    frame_part = total_frames % int(fps)
    total_secs = int(seconds)
    secs = total_secs % 60
    mins = (total_secs // 60) % 60
    hours = total_secs // 3600
    return f"{hours:02d}:{mins:02d}:{secs:02d}:{frame_part:02d}"


# ---------------------------------------------------------------------------
# Me / User
# ---------------------------------------------------------------------------

def get_me() -> dict:
    """Return the current authenticated user."""
    r = requests.get(f"{FRAMEIO_API_BASE}/me", headers=_headers())
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Asset / File
# ---------------------------------------------------------------------------

def get_asset(asset_id: str) -> dict:
    """Fetch file metadata from Frame.io v4. Returns the file dict."""
    account_id = _get_account_id()
    r = requests.get(
        f"{FRAMEIO_API_BASE}/accounts/{account_id}/files/{asset_id}",
        params={"include": "media_links.original,media_links.high_quality"},
        headers=_headers(),
    )
    r.raise_for_status()
    data = r.json()
    # v4 wraps responses in a "data" key
    return data.get("data", data)


def is_video_asset(asset: dict) -> bool:
    """Return True if the asset is a video file."""
    media_type = asset.get("media_type", "")
    return media_type.startswith("video/") or asset.get("name", "").lower().endswith(
        (".mp4", ".mov", ".mxf", ".avi")
    )


def download_asset(asset: dict, dest_dir: Path) -> Path:
    """
    Download the original video file for an asset to dest_dir.
    Returns the path to the downloaded file.
    """
    media_links = asset.get("media_links") or {}
    original = media_links.get("original") or {}
    high_quality = media_links.get("high_quality") or {}
    url = original.get("download_url") or high_quality.get("download_url")

    if not url:
        # Re-fetch with media_links explicitly included
        account_id = _get_account_id()
        r = requests.get(
            f"{FRAMEIO_API_BASE}/accounts/{account_id}/files/{asset['id']}",
            params={"include": "media_links.original,media_links.high_quality"},
            headers=_headers(),
        )
        r.raise_for_status()
        fresh = r.json().get("data", r.json())
        media_links = fresh.get("media_links") or {}
        original = media_links.get("original") or {}
        high_quality = media_links.get("high_quality") or {}
        url = original.get("download_url") or high_quality.get("download_url")

    if not url:
        raise ValueError(f"No downloadable URL found for asset {asset['id']}")

    filename = asset.get("name", f"{asset['id']}.mp4")
    dest_path = dest_dir / f"frameio_{asset['id']}_{filename}"

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with dest_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)

    return dest_path


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def post_comment(asset_id: str, text: str, timestamp_seconds: float, fps: float = DEFAULT_FPS) -> dict:
    """
    Post a timestamped comment on a Frame.io v4 file.
    timestamp_seconds is converted to HH:MM:SS:FF format.
    """
    account_id = _get_account_id()
    timestamp = _seconds_to_timestamp(timestamp_seconds, fps)
    payload = {
        "data": {
            "text": text,
            "timestamp": timestamp,
        }
    }
    r = requests.post(
        f"{FRAMEIO_API_BASE}/accounts/{account_id}/files/{asset_id}/comments",
        json=payload,
        headers=_headers(),
    )
    r.raise_for_status()
    return r.json()


def post_violation_comments(asset_id: str, violations: list, brand: str) -> None:
    """
    Post one comment per violation on the asset, pinned to the violation timestamp.
    """
    for v in violations:
        severity_tag = f"[{v.severity.upper()}]"
        text = (
            f"🚨 Brand Safety Violation {severity_tag}\n"
            f"Brand: {brand}\n"
            f"Rule violated: {v.prohibited_context}\n\n"
            f"{v.explanation}\n\n"
            f"Confidence: {v.confidence:.0%}"
        )
        try:
            post_comment(asset_id, text, v.timestamp_start)
        except Exception as e:
            print(f"    Failed to post comment at {v.timestamp_start}s: {e}")


def post_summary_comment(asset_id: str, brand: str, report) -> None:
    """Post a top-level summary comment at timestamp 0."""
    status_icon = "✅" if report.is_compliant else "❌"
    lines = [
        f"{status_icon} Brand Integration Audit — {brand}",
        f"Status: {report.delivery_status}",
        f"Appearances detected: {len(report.appearances)}",
        f"Violations: {len(report.violations)}",
    ]
    if report.contracted_screen_time_seconds > 0:
        lines.append(
            f"Screen time: {report.delivered_screen_time_seconds:.1f}s "
            f"of {report.contracted_screen_time_seconds:.1f}s contracted"
        )
    if report.violations:
        lines.append(f"  • {report.critical_count} critical  "
                     f"• {report.moderate_count} moderate  "
                     f"• {report.minor_count} minor")
    lines.append("\nPowered by Brand Integration Auditor + TwelveLabs")

    try:
        post_comment(asset_id, "\n".join(lines), timestamp_seconds=0)
    except Exception as e:
        print(f"    Failed to post summary comment: {e}")


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------

def get_workspaces(account_id: str | None = None) -> list[dict]:
    """Return all workspaces the current token has access to."""
    if not account_id:
        account_id = _get_account_id()
    r = requests.get(
        f"{FRAMEIO_API_BASE}/accounts/{account_id}/workspaces",
        headers=_headers(),
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        return data.get("data", [])
    return data


# ---------------------------------------------------------------------------
# Webhook registration
# ---------------------------------------------------------------------------

def register_webhook(workspace_id: str, url: str, account_id: str | None = None) -> dict:
    """
    Register a webhook for file.ready events on the given workspace.
    Returns the webhook object (including the one-time signing secret).
    """
    if not account_id:
        account_id = _get_account_id()
    payload = {
        "data": {
            "name": "Brand Integration Auditor",
            "url": url,
            "events": ["file.ready"],
        }
    }
    r = requests.post(
        f"{FRAMEIO_API_BASE}/accounts/{account_id}/workspaces/{workspace_id}/webhooks",
        json=payload,
        headers=_headers(),
    )
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def verify_webhook_signature(
    body: bytes,
    timestamp_header: str,
    signature_header: str,
    secret: str,
    max_age_seconds: int = 300,
) -> bool:
    """
    Verify the HMAC-SHA256 signature Frame.io sends with every webhook.

    Headers:
      X-Frameio-Request-Timestamp  — Unix epoch (seconds)
      X-Frameio-Signature          — "v0=<hex_digest>"
    """
    try:
        request_time = int(timestamp_header)
        if abs(time.time() - request_time) > max_age_seconds:
            return False
    except (ValueError, TypeError):
        return False

    message = f"v0:{timestamp_header}:{body.decode('latin-1')}"
    expected = "v0=" + hmac.new(
        bytes(secret, "latin-1"),
        msg=bytes(message, "latin-1"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)
