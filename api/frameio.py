"""
Frame.io v4 API client.

Handles asset fetching, video downloading, and posting compliance
violations back as timestamped comments on the asset.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

FRAMEIO_API_BASE = "https://api.frame.io/v4"
FRAMEIO_TOKEN = os.getenv("FRAMEIO_API_TOKEN", "").strip()
_account_id_cache: str = os.getenv("FRAMEIO_ACCOUNT_ID", "").strip()

# Adobe IMS token refresh endpoint
_IMS_TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"

# Refresh if token expires within this many seconds
_REFRESH_BUFFER_SECONDS = 300  # 5 minutes

# Default frame rate used when converting seconds → HH:MM:SS:FF timestamps.
DEFAULT_FPS = 24


def _parse_jwt_expiry(token: str) -> float | None:
    """
    Decode the JWT payload (no signature verification) and return the Unix
    timestamp (seconds) at which the token expires, or None if unparseable.
    Adobe IMS JWTs carry created_at (ms) and expires_in (ms) in the payload.
    """
    try:
        payload_b64 = token.split(".")[1]
        # Pad to a valid base64 length
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        created_at_ms = float(payload["created_at"])
        expires_in_ms = float(payload["expires_in"])
        return (created_at_ms + expires_in_ms) / 1000.0
    except Exception:
        return None


def _token_is_expiring() -> bool:
    """Return True if the current token is missing, expired, or expiring soon."""
    if not FRAMEIO_TOKEN:
        return True
    expiry = _parse_jwt_expiry(FRAMEIO_TOKEN)
    if expiry is None:
        return False  # Can't parse — assume still valid
    return time.time() >= (expiry - _REFRESH_BUFFER_SECONDS)


def _refresh_token() -> bool:
    """
    Use FRAMEIO_REFRESH_TOKEN to get a new access token from Adobe IMS.
    Updates FRAMEIO_TOKEN in memory and persists both tokens to .env.
    Returns True on success.
    """
    global FRAMEIO_TOKEN

    refresh_tok = os.getenv("FRAMEIO_REFRESH_TOKEN", "").strip()
    client_id = os.getenv("FRAMEIO_CLIENT_ID", "").strip()
    client_secret = os.getenv("FRAMEIO_CLIENT_SECRET", "").strip()

    if not refresh_tok or not client_id or not client_secret:
        print("[Frame.io] Cannot refresh token — missing FRAMEIO_REFRESH_TOKEN, CLIENT_ID, or CLIENT_SECRET")
        return False

    try:
        resp = requests.post(
            _IMS_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_tok,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[Frame.io] Token refresh request failed: {e}")
        return False

    new_access = data.get("access_token", "")
    new_refresh = data.get("refresh_token", "")

    if not new_access:
        print(f"[Frame.io] Token refresh returned no access_token: {data}")
        return False

    FRAMEIO_TOKEN = new_access
    os.environ["FRAMEIO_API_TOKEN"] = new_access
    if new_refresh:
        os.environ["FRAMEIO_REFRESH_TOKEN"] = new_refresh

    # Persist to .env
    _env_file = Path(__file__).parent.parent / ".env"
    if _env_file.exists():
        lines = _env_file.read_text().splitlines()

        def _upsert(key: str, value: str) -> None:
            for i, line in enumerate(lines):
                if line.startswith(f"{key} =") or line.startswith(f"{key}="):
                    lines[i] = f"{key} = {value}"
                    return
            lines.append(f"{key} = {value}")

        _upsert("FRAMEIO_API_TOKEN", new_access)
        if new_refresh:
            _upsert("FRAMEIO_REFRESH_TOKEN", new_refresh)
        _env_file.write_text("\n".join(lines) + "\n")

    print("[Frame.io] Access token refreshed successfully.")
    return True


def _ensure_valid_token() -> None:
    """Refresh the token if it is expired or about to expire."""
    if _token_is_expiring():
        _refresh_token()


def _headers() -> dict:
    _ensure_valid_token()
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


def post_review_decision(
    asset_id: str,
    decision: str,
    brand: str,
    notes: str | None = None,
) -> None:
    """Post the compliance review decision as a pinned comment at timestamp 0."""
    icons  = {"approved": "✅", "rejected": "❌", "escalated": "⚠️"}
    labels = {"approved": "APPROVED FOR DELIVERY", "rejected": "REJECTED — REVISIONS REQUIRED", "escalated": "ESCALATED FOR REVIEW"}

    lines = [
        f"{icons.get(decision, '📋')} Compliance Decision: {labels.get(decision, decision.upper())}",
        f"Brand: {brand}",
    ]
    if notes:
        lines.append(f"\nReviewer notes: {notes}")
    lines.append("\nReviewed via Brand Unsafe | Brand Compliance Auditor")

    try:
        post_comment(asset_id, "\n".join(lines), timestamp_seconds=0)
    except Exception as e:
        print(f"[Frame.io] Failed to post review decision: {e}")


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
# Custom Actions
# ---------------------------------------------------------------------------

def register_custom_action(
    account_id: str,
    name: str,
    url: str,
    description: str = "",
) -> dict:
    """
    Register a Custom Action that appears in the Frame.io asset context menu.
    Returns the created custom action object.
    """
    payload = {
        "data": {
            "name": name,
            "description": description,
            "url": url,
            "resource_types": ["file"],
        }
    }
    r = requests.post(
        f"{FRAMEIO_API_BASE}/accounts/{account_id}/custom-actions",
        json=payload,
        headers=_headers(),
    )
    r.raise_for_status()
    return r.json()


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
