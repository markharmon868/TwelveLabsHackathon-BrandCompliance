"""Pydantic schemas for all API request/response shapes."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Violation + Appearance
# ---------------------------------------------------------------------------

class ViolationSchema(BaseModel):
    timestamp_start: float
    timestamp_end: float
    brand: str
    prohibited_context: str
    explanation: str
    confidence: float
    severity: Literal["minor", "moderate", "critical"]


class AppearanceSchema(BaseModel):
    timestamp_start: float
    timestamp_end: float
    brand: str
    confidence: float
    status: Literal["compliant", "violation", "needs_review"]
    explanation: str
    violation: ViolationSchema | None = None


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

class ReportSchema(BaseModel):
    brand: str
    video_filename: str
    index_id: str
    video_id: str
    contracted_screen_time_seconds: float
    delivered_screen_time_seconds: float
    screen_time_gap_seconds: float
    is_under_delivered: bool
    delivery_status: Literal["COMPLIANT", "VIOLATION", "UNDER-DELIVERED"]
    is_compliant: bool
    appearances: list[AppearanceSchema]
    violations: list[ViolationSchema]
    # counts
    compliant_count: int
    needs_review_count: int
    critical_count: int
    moderate_count: int
    minor_count: int


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

class JobSchema(BaseModel):
    job_id: str
    status: Literal["queued", "indexing", "analyzing", "complete", "failed"]
    progress_message: str
    brand: str
    video_filename: str
    guidelines_filename: str
    video_url: str | None = None    # relative URL to stream the video, e.g. /videos/uuid.mp4
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    report: ReportSchema | None = None


class JobListSchema(BaseModel):
    jobs: list[JobSchema]
    total: int


# ---------------------------------------------------------------------------
# Guidelines sample listing
# ---------------------------------------------------------------------------

class GuidelinesSampleSchema(BaseModel):
    filename: str
    brand: str
    prohibited_count: int
    required_count: int
    contracted_screen_time_seconds: float
