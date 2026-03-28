"""
In-memory job store and background processing.

Each job runs in its own thread (TwelveLabs SDK is synchronous).
Job state is kept in a module-level dict — sufficient for the hackathon.
For production this would be replaced with a database + task queue.
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from brand_compliance import (
    Guidelines,
    ComplianceReport,
    create_index,
    upload_video,
    analyze_brand_compliance,
)
from brand_compliance.models import Appearance, Violation
from .schemas import (
    AppearanceSchema,
    GuidelinesSampleSchema,
    JobSchema,
    ReportSchema,
    ViolationSchema,
)

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_jobs: dict[str, dict] = {}
_lock = threading.Lock()

GUIDELINES_DIR = Path(__file__).parent.parent / "guidelines"
VIDEOS_DIR = Path(__file__).parent.parent / "videos"


# ---------------------------------------------------------------------------
# Public API used by routes
# ---------------------------------------------------------------------------

def create_job(
    video_path: Path,
    guidelines: Guidelines,
    video_filename: str,
    guidelines_filename: str,
) -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress_message": "Job queued — waiting to start",
            "brand": guidelines.brand,
            "video_filename": video_filename,
            "guidelines_filename": guidelines_filename,
            "video_url": f"/videos/{video_path.name}",
            "created_at": datetime.now(timezone.utc),
            "completed_at": None,
            "error": None,
            "report": None,
        }

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, video_path, guidelines),
        daemon=True,
    )
    thread.start()
    return job_id


def get_job(job_id: str) -> JobSchema | None:
    with _lock:
        raw = _jobs.get(job_id)
    if raw is None:
        return None
    return JobSchema(**raw)


def list_jobs() -> list[JobSchema]:
    with _lock:
        snapshot = list(_jobs.values())
    snapshot.sort(key=lambda j: j["created_at"], reverse=True)
    return [JobSchema(**j) for j in snapshot]


def list_sample_guidelines() -> list[GuidelinesSampleSchema]:
    samples = []
    for path in sorted(GUIDELINES_DIR.glob("*.json")):
        try:
            with path.open() as f:
                data = json.load(f)
            g = Guidelines.from_dict(data)
            samples.append(GuidelinesSampleSchema(
                filename=path.name,
                brand=g.brand,
                prohibited_count=len(g.prohibited_contexts),
                required_count=len(g.required_contexts),
                contracted_screen_time_seconds=g.contracted_screen_time_seconds,
            ))
        except Exception:
            continue
    return samples


# ---------------------------------------------------------------------------
# Background job runner
# ---------------------------------------------------------------------------

def _set_status(job_id: str, status: str, message: str) -> None:
    with _lock:
        _jobs[job_id]["status"] = status
        _jobs[job_id]["progress_message"] = message


def _run_job(job_id: str, video_path: Path, guidelines: Guidelines) -> None:
    try:
        # --- Step 1: create / reuse index ---
        _set_status(job_id, "indexing", "Creating or locating TwelveLabs index...")
        index_name = guidelines.brand.lower().replace(" ", "_") + "_compliance"
        index_id = create_index(index_name)

        # --- Step 2: upload and index video ---
        _set_status(job_id, "indexing", "Uploading video and waiting for indexing to complete...")
        video_id = upload_video(index_id, video_path)

        # --- Step 3: run compliance analysis ---
        _set_status(job_id, "analyzing", "Scanning for brand appearances and violations...")
        appearances, violations = analyze_brand_compliance(
            index_id=index_id,
            video_id=video_id,
            guidelines=guidelines,
        )

        # --- Step 4: build report ---
        report = ComplianceReport(
            brand=guidelines.brand,
            video_path=str(video_path),
            index_id=index_id,
            video_id=video_id,
            contracted_screen_time_seconds=guidelines.contracted_screen_time_seconds,
            appearances=appearances,
            violations=violations,
        )

        with _lock:
            _jobs[job_id]["status"] = "complete"
            _jobs[job_id]["progress_message"] = "Audit complete"
            _jobs[job_id]["completed_at"] = datetime.now(timezone.utc)
            _jobs[job_id]["report"] = _serialize_report(
                report,
                video_filename=_jobs[job_id]["video_filename"],
            )

    except Exception as exc:
        with _lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["progress_message"] = f"Job failed: {exc}"
            _jobs[job_id]["error"] = str(exc)
            _jobs[job_id]["completed_at"] = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Internal serialization helpers
# ---------------------------------------------------------------------------

def _serialize_violation(v: Violation) -> ViolationSchema:
    return ViolationSchema(
        timestamp_start=v.timestamp_start,
        timestamp_end=v.timestamp_end,
        brand=v.brand,
        prohibited_context=v.prohibited_context,
        explanation=v.explanation,
        confidence=v.confidence,
        severity=v.severity,
    )


def _serialize_appearance(a: Appearance) -> AppearanceSchema:
    return AppearanceSchema(
        timestamp_start=a.timestamp_start,
        timestamp_end=a.timestamp_end,
        brand=a.brand,
        confidence=a.confidence,
        status=a.status,
        explanation=a.explanation,
        violation=_serialize_violation(a.violation) if a.violation else None,
    )


def _serialize_report(report: ComplianceReport, video_filename: str) -> ReportSchema:
    return ReportSchema(
        brand=report.brand,
        video_filename=video_filename,
        index_id=report.index_id,
        video_id=report.video_id,
        contracted_screen_time_seconds=report.contracted_screen_time_seconds,
        delivered_screen_time_seconds=report.delivered_screen_time_seconds,
        screen_time_gap_seconds=report.screen_time_gap_seconds,
        is_under_delivered=report.is_under_delivered,
        delivery_status=report.delivery_status,
        is_compliant=report.is_compliant,
        appearances=[_serialize_appearance(a) for a in report.appearances],
        violations=[_serialize_violation(v) for v in report.violations],
        compliant_count=report.compliant_count,
        needs_review_count=report.needs_review_count,
        critical_count=report.critical_count,
        moderate_count=report.moderate_count,
        minor_count=report.minor_count,
    )
