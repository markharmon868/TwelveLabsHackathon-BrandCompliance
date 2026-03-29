"""
Brand Integration Auditor — FastAPI backend

Endpoints:
  POST   /jobs                    Upload video + guidelines, start audit job
  GET    /jobs                    List all jobs
  GET    /jobs/{job_id}           Get job status and report (when complete)
  DELETE /jobs/{job_id}           Remove a job from the store
  GET    /guidelines/samples      List built-in sample guidelines files
  GET    /guidelines/samples/{filename}   Return a sample guidelines file as JSON
  GET    /health                  Health check
"""

import json
import re
import shutil
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from brand_compliance import Guidelines
from .webhook_routes import router as webhook_router
from .oauth_routes import router as oauth_router
from .frameio_routes import router as frameio_router
from .jobs import (
    GUIDELINES_DIR,
    VIDEOS_DIR,
    create_job,
    get_job,
    list_jobs,
    list_sample_guidelines,
    review_job,
)
from .schemas import GuidelinesSampleSchema, JobListSchema, JobSchema, ReviewRequestSchema

app = FastAPI(
    title="Brand Integration Auditor",
    description="AI-powered brand compliance scanning for post-production",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*", "X-TwelveLabs-Key"],
)

# Serve uploaded video files so the frontend can play them back
VIDEOS_DIR.mkdir(exist_ok=True)
app.mount("/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")

app.include_router(webhook_router)
app.include_router(oauth_router)
app.include_router(frameio_router)

# Serve the compiled React frontend (production build)
_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/key", tags=["meta"])
def validate_key(x_twelvelabs_key: str | None = Header(default=None)) -> dict:
    """Validate a TwelveLabs API key by making a lightweight API call."""
    key = (x_twelvelabs_key or "").strip()
    if not key:
        raise HTTPException(status_code=401, detail="No API key provided.")
    try:
        from brand_compliance.client import get_client
        client = get_client(api_key=key)
        list(client.indexes.list(page_limit=1))
        return {"valid": True}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Key validation failed: {e}")


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@app.post(
    "/jobs",
    response_model=JobSchema,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["jobs"],
    summary="Submit a video for brand compliance auditing",
)
async def submit_job(
    video_file: UploadFile = File(..., description="Video file (MP4 or MOV)"),
    guidelines_file: UploadFile | None = File(
        default=None,
        description="Brand guidelines JSON file (upload this OR provide guidelines_json)",
    ),
    guidelines_json: str | None = Form(
        default=None,
        description="Raw guidelines JSON string (alternative to uploading a file)",
    ),
    sample_guidelines: str | None = Form(
        default=None,
        description="Filename of a built-in sample guidelines file (e.g. pureflow_water.json)",
    ),
    x_twelvelabs_key: str | None = Header(default=None),
) -> JobSchema:
    """
    Start a brand compliance audit job.

    Supply the video and guidelines in one of three ways:
    - Upload a `guidelines_file` (JSON)
    - Pass raw JSON in `guidelines_json`
    - Name a built-in sample via `sample_guidelines`
    """
    # --- Resolve guidelines ---
    guidelines_raw: dict | None = None
    guidelines_filename = "inline"

    if guidelines_file is not None:
        try:
            content = await guidelines_file.read()
            guidelines_raw = json.loads(content)
            guidelines_filename = guidelines_file.filename or "uploaded.json"
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid guidelines JSON file: {e}",
            )
    elif guidelines_json is not None:
        try:
            guidelines_raw = json.loads(guidelines_json)
            guidelines_filename = "inline.json"
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid guidelines_json: {e}",
            )
    elif sample_guidelines is not None:
        sample_path = GUIDELINES_DIR / sample_guidelines
        if not sample_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Sample guidelines '{sample_guidelines}' not found.",
            )
        with sample_path.open() as f:
            guidelines_raw = json.load(f)
        guidelines_filename = sample_guidelines
    else:
        raise HTTPException(
            status_code=422,
            detail="Provide one of: guidelines_file, guidelines_json, or sample_guidelines.",
        )

    try:
        guidelines = Guidelines.from_dict(guidelines_raw)
    except KeyError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Guidelines missing required field: {e}",
        )

    # --- Save uploaded video to disk ---
    suffix = Path(video_file.filename or "video.mp4").suffix or ".mp4"
    video_filename = video_file.filename or "video.mp4"
    saved_video_path = VIDEOS_DIR / f"{uuid.uuid4()}{suffix}"
    VIDEOS_DIR.mkdir(exist_ok=True)

    with saved_video_path.open("wb") as f:
        shutil.copyfileobj(video_file.file, f)

    # --- Create and launch job ---
    job_id = create_job(
        video_path=saved_video_path,
        guidelines=guidelines,
        video_filename=video_filename,
        guidelines_filename=guidelines_filename,
        api_key=x_twelvelabs_key or None,
    )

    job = get_job(job_id)
    return job


@app.get("/jobs", response_model=JobListSchema, tags=["jobs"])
def get_jobs() -> JobListSchema:
    """Return all jobs, most recent first."""
    jobs = list_jobs()
    return JobListSchema(jobs=jobs, total=len(jobs))


@app.get("/jobs/{job_id}", response_model=JobSchema, tags=["jobs"])
def get_job_status(job_id: str) -> JobSchema:
    """
    Poll this endpoint for job status.
    `status` progresses: queued → indexing → analyzing → complete | failed
    The `report` field is populated when status is `complete`.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@app.post("/jobs/{job_id}/review", response_model=JobSchema, tags=["jobs"])
def submit_review(job_id: str, body: ReviewRequestSchema) -> JobSchema:
    """
    Record a compliance review decision (approved / rejected / escalated).
    If the job originated from Frame.io, posts the decision as a comment on the asset.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job.status != "complete":
        raise HTTPException(status_code=422, detail="Can only review completed jobs.")

    updated = review_job(job_id, body.decision, body.notes)

    # Post decision back to Frame.io if we have an asset ID
    if job.frame_io_asset_id:
        try:
            from .frameio import post_review_decision
            post_review_decision(
                asset_id=job.frame_io_asset_id,
                decision=body.decision,
                brand=job.brand,
                notes=body.notes,
            )
        except Exception as e:
            print(f"[review] Failed to post decision to Frame.io: {e}")

    return updated


@app.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["jobs"])
def delete_job(job_id: str) -> None:
    """Remove a job from the in-memory store."""
    from .jobs import _cache, _cache_lock
    with _cache_lock:
        if job_id not in _cache:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
        del _cache[job_id]
    from .jobs import _get_conn
    conn = _get_conn()
    conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Guidelines
# ---------------------------------------------------------------------------

@app.get(
    "/guidelines/samples",
    response_model=list[GuidelinesSampleSchema],
    tags=["guidelines"],
)
def get_sample_guidelines() -> list[GuidelinesSampleSchema]:
    """List the built-in sample brand guidelines files."""
    return list_sample_guidelines()


@app.get(
    "/guidelines/samples/{filename}",
    tags=["guidelines"],
    summary="Return the contents of a sample guidelines file",
)
def get_sample_guidelines_file(filename: str) -> JSONResponse:
    _validate_filename(filename)
    path = GUIDELINES_DIR / filename
    if not path.exists() or path.suffix != ".json":
        raise HTTPException(status_code=404, detail=f"Sample '{filename}' not found.")
    with path.open() as f:
        data = json.load(f)
    return JSONResponse(content=data)


@app.post(
    "/guidelines/samples",
    status_code=status.HTTP_201_CREATED,
    tags=["guidelines"],
    summary="Create a new guidelines file",
)
def create_sample_guidelines(data: dict = Body(...)) -> JSONResponse:
    brand = (data.get("brand") or "").strip()
    if not brand:
        raise HTTPException(status_code=422, detail="'brand' field is required.")

    base = re.sub(r"[^a-z0-9]+", "_", brand.lower()).strip("_")
    filename = f"{base}.json"
    path = GUIDELINES_DIR / filename

    # Avoid overwriting an existing file
    if path.exists():
        i = 2
        while (GUIDELINES_DIR / f"{base}_{i}.json").exists():
            i += 1
        filename = f"{base}_{i}.json"
        path = GUIDELINES_DIR / filename

    GUIDELINES_DIR.mkdir(exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)

    return JSONResponse(content={"filename": filename}, status_code=201)


@app.put(
    "/guidelines/samples/{filename}",
    tags=["guidelines"],
    summary="Update an existing guidelines file",
)
def update_sample_guidelines(filename: str, data: dict = Body(...)) -> JSONResponse:
    _validate_filename(filename)
    path = GUIDELINES_DIR / filename
    if not path.exists() or path.suffix != ".json":
        raise HTTPException(status_code=404, detail=f"Guideline '{filename}' not found.")

    with path.open("w") as f:
        json.dump(data, f, indent=2)

    return JSONResponse(content={"filename": filename})


@app.delete(
    "/guidelines/samples/{filename}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["guidelines"],
    summary="Delete a guidelines file",
)
def delete_sample_guidelines(filename: str) -> None:
    _validate_filename(filename)
    path = GUIDELINES_DIR / filename
    if not path.exists() or path.suffix != ".json":
        raise HTTPException(status_code=404, detail=f"Guideline '{filename}' not found.")
    path.unlink()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_filename(filename: str) -> None:
    """Prevent path-traversal attacks."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")


# ---------------------------------------------------------------------------
# React SPA — serve frontend/dist in production
# Must be registered LAST so API routes take priority.
# ---------------------------------------------------------------------------

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str) -> FileResponse:
        """Serve index.html for any route not matched by the API."""
        return FileResponse(str(_FRONTEND_DIST / "index.html"))
