"""
Frame.io webhook endpoint.

Frame.io POSTs to /webhooks/frameio when an asset is created.
We fetch the asset, download it if it's a video, run the compliance
audit, and post violations back as timestamped comments.
"""

import json
import os
import threading
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request, status

from brand_compliance import Guidelines
from brand_compliance.models import ComplianceReport
from .frameio import (
    download_asset,
    get_asset,
    is_video_asset,
    post_summary_comment,
    post_violation_comments,
    verify_webhook_signature,
)
from .jobs import (
    GUIDELINES_DIR,
    VIDEOS_DIR,
    _cache,
    _cache_lock,
    _run_job,
    create_job,
)
from .frameio_config import load_config

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

FRAMEIO_WEBHOOK_SECRET = os.getenv("FRAMEIO_WEBHOOK_SECRET", "").strip()


@router.post("/frameio", status_code=status.HTTP_200_OK)
async def frameio_webhook(
    request: Request,
    x_frameio_request_timestamp: str = Header(default=""),
    x_frameio_signature: str = Header(default=""),
) -> dict:
    """
    Receives Frame.io webhook events.
    Triggers a brand compliance audit when a video asset is created.
    """
    body = await request.body()

    # --- Signature verification (skip if no secret configured) ---
    if FRAMEIO_WEBHOOK_SECRET:
        valid = verify_webhook_signature(
            body=body,
            timestamp_header=x_frameio_request_timestamp,
            signature_header=x_frameio_signature,
            secret=FRAMEIO_WEBHOOK_SECRET,
        )
        if not valid:
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # v4 payload: {"data": {"type": "file.ready", "resource": {"id": "...", "type": "file"}, ...}}
    # v2 payload: {"name": "asset.created", "resource": {"id": "..."}}
    data = payload.get("data", payload)
    event_name = data.get("type") or payload.get("name", "")
    resource = data.get("resource") or payload.get("resource", {})
    asset_id = resource.get("id")

    print(f"[Frame.io webhook] event={event_name} asset_id={asset_id}")

    # Accept file.ready (v4) or asset.created (v2 legacy)
    handled_events = {"file.ready", "file.upload.completed", "asset.created"}
    if event_name not in handled_events or not asset_id:
        return {"status": "ignored", "reason": f"event '{event_name}' not handled"}

    # Run audit in background thread to return 200 immediately to Frame.io
    thread = threading.Thread(
        target=_process_frameio_asset,
        args=(asset_id, "webhook"),
        daemon=True,
    )
    thread.start()

    return {"status": "accepted", "asset_id": asset_id}


@router.post("/frameio-action", status_code=status.HTTP_200_OK)
async def frameio_custom_action(
    request: Request,
    x_frameio_request_timestamp: str = Header(default=""),
    x_frameio_signature: str = Header(default=""),
) -> dict:
    """
    Receives Frame.io Custom Action triggers.
    Fires when an editor right-clicks an asset and chooses
    'Submit for Compliance Review' in Frame.io.
    """
    body = await request.body()

    if FRAMEIO_WEBHOOK_SECRET:
        valid = verify_webhook_signature(
            body=body,
            timestamp_header=x_frameio_request_timestamp,
            signature_header=x_frameio_signature,
            secret=FRAMEIO_WEBHOOK_SECRET,
        )
        if not valid:
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    data = payload.get("data", payload)
    resource = data.get("resource") or {}
    asset_id = resource.get("id")

    if not asset_id:
        return {"status": "ignored", "reason": "no asset_id in payload"}

    print(f"[Frame.io custom action] asset_id={asset_id}")

    thread = threading.Thread(
        target=_process_frameio_asset,
        args=(asset_id, "custom_action"),
        daemon=True,
    )
    thread.start()

    return {"status": "accepted", "asset_id": asset_id}


def _process_frameio_asset(asset_id: str, source: str = "webhook") -> None:
    """
    Background task: fetch asset → download video → run audit → post comments.
    """
    print(f"[Frame.io] Processing asset {asset_id}...")

    # --- Fetch asset metadata ---
    try:
        asset = get_asset(asset_id)
    except Exception as e:
        print(f"[Frame.io] Failed to fetch asset {asset_id}: {e}")
        return

    if not is_video_asset(asset):
        print(f"[Frame.io] Asset {asset_id} is not a video — skipping")
        return

    print(f"[Frame.io] Video asset: {asset.get('name')} ({asset.get('filetype')})")

    # --- Load guidelines from config (falls back to first available) ---
    cfg = load_config()
    default_file = cfg.get("default_guidelines", "")
    guidelines_path = GUIDELINES_DIR / default_file if default_file else None

    if not guidelines_path or not guidelines_path.exists():
        available = sorted(GUIDELINES_DIR.glob("*.json"))
        if not available:
            print("[Frame.io] No guidelines files found — skipping audit")
            return
        guidelines_path = available[0]

    try:
        import json as _json
        with guidelines_path.open() as f:
            guidelines = Guidelines.from_dict(_json.load(f))
    except Exception as e:
        print(f"[Frame.io] Failed to load guidelines: {e}")
        return

    # --- Download video ---
    try:
        VIDEOS_DIR.mkdir(exist_ok=True)
        video_path = download_asset(asset, VIDEOS_DIR)
        print(f"[Frame.io] Downloaded to {video_path}")
    except Exception as e:
        print(f"[Frame.io] Failed to download asset: {e}")
        return

    # --- Create and run compliance job ---
    job_id = create_job(
        video_path=video_path,
        guidelines=guidelines,
        video_filename=asset.get("name", video_path.name),
        guidelines_filename=guidelines_path.name,
        frame_io_asset_id=asset_id,
        source=source,
    )
    print(f"[Frame.io] Created job {job_id} for asset {asset_id}")

    # Wait for job to complete by polling the in-memory store
    import time
    max_wait = 1800  # 30 minutes
    poll_interval = 10
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        with _cache_lock:
            job = _cache.get(job_id)
        if not job:
            break
        if job["status"] == "complete":
            report_schema = job.get("report")
            if report_schema:
                _post_results_to_frameio(asset_id, asset, report_schema, guidelines)
            break
        if job["status"] == "failed":
            print(f"[Frame.io] Job {job_id} failed: {job.get('error')}")
            break

    print(f"[Frame.io] Done processing asset {asset_id}")


def _post_results_to_frameio(asset_id: str, asset: dict, report_schema, guidelines: Guidelines) -> None:
    """Post the audit summary and violation comments back to Frame.io."""
    print(f"[Frame.io] Posting results to asset {asset_id}...")

    # Build a minimal ComplianceReport-like object from the schema for helpers
    from brand_compliance.models import ComplianceReport, Appearance, Violation

    appearances = [
        Appearance(
            timestamp_start=a.timestamp_start,
            timestamp_end=a.timestamp_end,
            brand=a.brand,
            confidence=a.confidence,
            status=a.status,
            explanation=a.explanation,
            violation=Violation(
                timestamp_start=a.violation.timestamp_start,
                timestamp_end=a.violation.timestamp_end,
                brand=a.violation.brand,
                prohibited_context=a.violation.prohibited_context,
                explanation=a.violation.explanation,
                confidence=a.violation.confidence,
                severity=a.violation.severity,
            ) if a.violation else None,
        )
        for a in report_schema.appearances
    ]

    violations = [
        Violation(
            timestamp_start=v.timestamp_start,
            timestamp_end=v.timestamp_end,
            brand=v.brand,
            prohibited_context=v.prohibited_context,
            explanation=v.explanation,
            confidence=v.confidence,
            severity=v.severity,
        )
        for v in report_schema.violations
    ]

    report = ComplianceReport(
        brand=report_schema.brand,
        video_path=asset.get("name", ""),
        index_id=report_schema.index_id,
        video_id=report_schema.video_id,
        contracted_screen_time_seconds=report_schema.contracted_screen_time_seconds,
        appearances=appearances,
        violations=violations,
    )

    try:
        post_summary_comment(asset_id, guidelines.brand, report)
        print(f"[Frame.io] Posted summary comment")
    except Exception as e:
        print(f"[Frame.io] Failed to post summary: {e}")

    if violations:
        post_violation_comments(asset_id, violations, guidelines.brand)
        print(f"[Frame.io] Posted {len(violations)} violation comment(s)")
