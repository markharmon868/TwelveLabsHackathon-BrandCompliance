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
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from brand_compliance import Guidelines
from .jobs import (
    GUIDELINES_DIR,
    VIDEOS_DIR,
    create_job,
    get_job,
    list_jobs,
    list_sample_guidelines,
)
from .schemas import GuidelinesSampleSchema, JobListSchema, JobSchema

app = FastAPI(
    title="Brand Integration Auditor",
    description="AI-powered brand compliance scanning for post-production",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this when deploying
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded video files so the frontend can play them back
VIDEOS_DIR.mkdir(exist_ok=True)
app.mount("/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


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


@app.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["jobs"])
def delete_job(job_id: str) -> None:
    """Remove a job from the in-memory store."""
    from .jobs import _jobs, _lock
    with _lock:
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
        del _jobs[job_id]


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
    path = GUIDELINES_DIR / filename
    if not path.exists() or path.suffix != ".json":
        raise HTTPException(status_code=404, detail=f"Sample '{filename}' not found.")
    with path.open() as f:
        data = json.load(f)
    return JSONResponse(content=data)
