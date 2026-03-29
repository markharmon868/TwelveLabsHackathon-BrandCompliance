"""
Job store with SQLite persistence.

Each job is stored as a JSON blob so the full JobSchema survives server
restarts.  The threading model (one daemon thread per job) is unchanged.
"""

import json
import os
import sqlite3
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
# Paths
# ---------------------------------------------------------------------------

_DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent.parent)))
GUIDELINES_DIR = Path(__file__).parent.parent / "guidelines"
VIDEOS_DIR = _DATA_DIR / "videos"
DB_PATH = _DATA_DIR / "jobs.db"

# ---------------------------------------------------------------------------
# SQLite setup  (one connection per thread via thread-local storage)
# ---------------------------------------------------------------------------

_local = threading.local()
_schema_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    """Return a per-thread SQLite connection, creating it on first use."""
    if not hasattr(_local, "conn"):
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
        _ensure_schema(conn)
    return _local.conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    with _schema_lock:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id   TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                data     TEXT NOT NULL
            )
            """
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Low-level read / write helpers
# ---------------------------------------------------------------------------

def _write_job(job: dict) -> None:
    """Persist (insert or replace) a job dict."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO jobs (job_id, created_at, data) VALUES (?, ?, ?)",
        (job["job_id"], job["created_at"].isoformat(), _dump(job)),
    )
    conn.commit()


def _dump(job: dict) -> str:
    """Serialize job dict to JSON, handling datetime + Pydantic objects."""
    def default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):  # Pydantic v2
            return obj.model_dump()
        if hasattr(obj, "dict"):        # Pydantic v1
            return obj.dict()
        raise TypeError(f"Not serializable: {type(obj)}")

    return json.dumps(job, default=default)


def _load(row_data: str) -> dict:
    """Deserialize a job dict from JSON, restoring datetime fields."""
    raw = json.loads(row_data)
    for field in ("created_at", "completed_at", "reviewed_at"):
        if raw.get(field):
            raw[field] = datetime.fromisoformat(raw[field])
    return raw


# ---------------------------------------------------------------------------
# In-memory write-through cache (avoids repeated DB reads during hot paths)
# ---------------------------------------------------------------------------

_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()


def _cache_put(job: dict) -> None:
    with _cache_lock:
        _cache[job["job_id"]] = job


def _cache_get(job_id: str) -> dict | None:
    with _cache_lock:
        return _cache.get(job_id)


def _load_all_from_db() -> None:
    """Populate the in-memory cache from SQLite on startup."""
    conn = _get_conn()
    for row in conn.execute("SELECT data FROM jobs ORDER BY created_at DESC"):
        job = _load(row["data"])
        _cache[job["job_id"]] = job


# Eagerly populate cache at import time so list_jobs() is fast.
_load_all_from_db()


# ---------------------------------------------------------------------------
# Public API used by routes
# ---------------------------------------------------------------------------

def create_job(
    video_path: Path,
    guidelines: Guidelines,
    video_filename: str,
    guidelines_filename: str,
    frame_io_asset_id: str | None = None,
    source: str = "upload",
    api_key: str | None = None,
) -> str:
    job_id = str(uuid.uuid4())
    job: dict = {
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
        "review_status": None,
        "review_notes": None,
        "reviewed_at": None,
        "frame_io_asset_id": frame_io_asset_id,
        "source": source,
        "_api_key": api_key,  # not exposed in JobSchema, stripped on serialisation
    }
    _cache_put(job)
    _write_job(job)

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, video_path, guidelines),
        daemon=True,
    )
    thread.start()
    return job_id


def get_job(job_id: str) -> JobSchema | None:
    raw = _cache_get(job_id)
    if raw is None:
        return None
    return JobSchema(**raw)


def list_jobs() -> list[JobSchema]:
    with _cache_lock:
        snapshot = list(_cache.values())
    snapshot.sort(key=lambda j: j["created_at"], reverse=True)
    return [JobSchema(**j) for j in snapshot]


def review_job(job_id: str, decision: str, notes: str | None) -> JobSchema | None:
    """Record a compliance review decision on a completed job."""
    with _cache_lock:
        job = _cache.get(job_id)
        if job is None:
            return None
        job["review_status"] = decision
        job["review_notes"] = notes
        job["reviewed_at"] = datetime.now(timezone.utc)
    _write_job(job)
    return JobSchema(**job)


def list_sample_guidelines() -> list[GuidelinesSampleSchema]:
    samples = []
    for path in sorted(GUIDELINES_DIR.glob("*.json")):
        try:
            with path.open() as f:
                data = json.load(f)
            from brand_compliance.models import Guidelines as GL
            g = GL.from_dict(data)
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
    with _cache_lock:
        job = _cache.get(job_id)
        if job:
            job["status"] = status
            job["progress_message"] = message
    if job:
        _write_job(job)


def _run_job(job_id: str, video_path: Path, guidelines: Guidelines) -> None:
    api_key: str | None = (_cache.get(job_id) or {}).get("_api_key")

    try:
        # --- Step 1: create / reuse index ---
        _set_status(job_id, "indexing", "Creating or locating TwelveLabs index...")
        index_name = guidelines.brand.lower().replace(" ", "_") + "_compliance"
        index_id = create_index(index_name, api_key=api_key)

        # --- Step 2: upload and index video ---
        _set_status(job_id, "indexing", "Uploading video and waiting for indexing to complete...")
        video_id = upload_video(index_id, video_path, api_key=api_key)

        # --- Step 3: run compliance analysis ---
        _set_status(job_id, "analyzing", "Scanning for brand appearances and violations...")
        appearances, violations = analyze_brand_compliance(
            index_id=index_id,
            video_id=video_id,
            guidelines=guidelines,
            api_key=api_key,
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

        with _cache_lock:
            job = _cache.get(job_id)
            if job:
                job["status"] = "complete"
                job["progress_message"] = "Audit complete"
                job["completed_at"] = datetime.now(timezone.utc)
                job["report"] = _serialize_report(
                    report,
                    video_filename=job["video_filename"],
                )
        if job:
            _write_job(job)

    except Exception as exc:
        with _cache_lock:
            job = _cache.get(job_id)
            if job:
                job["status"] = "failed"
                job["progress_message"] = f"Job failed: {exc}"
                job["error"] = str(exc)
                job["completed_at"] = datetime.now(timezone.utc)
        if job:
            _write_job(job)


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
