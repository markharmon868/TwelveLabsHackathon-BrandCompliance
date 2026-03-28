"""
Frame.io API client.

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

FRAMEIO_API_BASE = "https://api.frame.io/v2"
FRAMEIO_TOKEN = os.getenv("FRAMEIO_API_TOKEN", "").strip()

# Default frame rate used when converting seconds → frame numbers for comments.
# Frame.io comment timestamps are in frames, not seconds.
DEFAULT_FPS = 24


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {FRAMEIO_TOKEN}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------

def get_asset(asset_id: str) -> dict:
    """Fetch asset metadata from Frame.io. Returns the full asset dict."""
    r = requests.get(f"{FRAMEIO_API_BASE}/assets/{asset_id}", headers=_headers())
    r.raise_for_status()
    return r.json()


def is_video_asset(asset: dict) -> bool:
    """Return True if the asset is an uploadable video file."""
    filetype = asset.get("filetype", "")
    asset_type = asset.get("type", "")
    return asset_type == "file" and (
        filetype.startswith("video/") or
        asset.get("name", "").lower().endswith((".mp4", ".mov", ".mxf", ".avi"))
    )


def download_asset(asset: dict, dest_dir: Path) -> Path:
    """
    Download the original video file for an asset to dest_dir.
    Returns the path to the downloaded file.
    """
    url = asset.get("original")
    if not url:
        # Fall back to highest quality transcode
        downloads = asset.get("downloads", {})
        url = downloads.get("h264_1080_best") or downloads.get("h264_720") or downloads.get("h264_540")
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
    Post a timestamped comment on a Frame.io asset.
    timestamp_seconds is converted to frame number (Frame.io uses frames).
    """
    frame_number = int(timestamp_seconds * fps)
    payload = {
        "text": text,
        "timestamp": frame_number,
    }
    r = requests.post(
        f"{FRAMEIO_API_BASE}/assets/{asset_id}/comments",
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
# Teams
# ---------------------------------------------------------------------------

def get_teams() -> list[dict]:
    """Return all teams the current token has access to."""
    r = requests.get(f"{FRAMEIO_API_BASE}/teams", headers=_headers())
    r.raise_for_status()
    return r.json()


def get_me() -> dict:
    """Return the current authenticated user."""
    r = requests.get(f"{FRAMEIO_API_BASE}/me", headers=_headers())
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Webhook registration
# ---------------------------------------------------------------------------

def register_webhook(team_id: str, url: str) -> dict:
    """
    Register a webhook for asset.created events on the given team.
    Returns the webhook object (including the one-time signing secret).
    """
    payload = {
        "name": "Brand Integration Auditor",
        "url": url,
        "actions": ["asset.created"],
    }
    r = requests.post(
        f"{FRAMEIO_API_BASE}/teams/{team_id}/hooks",
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
    # Replay attack guard
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
