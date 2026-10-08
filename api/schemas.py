"""Typed v1 documents from docs/interfaces/api.md (snake_case, seconds)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


JobState = Literal["queued", "running", "completed", "failed", "cancelled"]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorBody(BaseModel):
    error: ErrorDetail


class Example(BaseModel):
    example_id: str
    title: str
    expected_outcome: Literal["fall", "no_fall"]
    video_url: str
    duration_seconds: float
    analysis_mode: Literal["cached", "on_demand"]
    model_version: str | None
    provenance: str


class ExamplesResponse(BaseModel):
    examples: list[Example]


class ExampleJobRequest(BaseModel):
    example_id: str


class Job(BaseModel):
    job_id: str
    state: JobState
    progress: float | None = Field(ge=0, le=1)
    source_kind: Literal["example", "upload"]
    created_at_utc: str
    model_version: str | None
    result_url: str | None
    error: ErrorDetail | None


class Prediction(BaseModel):
    timestamp_seconds: float
    fall_probability: float = Field(ge=0, le=1)
    window_start_seconds: float | None = None
    source_pose_count: int | None = None
    inference_ms: float | None = None
    urgency: float | None = None
    reliability: float | None = None


class Pose(BaseModel):
    timestamp_seconds: float
    bbox_xyxy: list[float] = Field(min_length=4, max_length=4)
    keypoints: list[list[float]] = Field(min_length=17, max_length=17)


class Incident(BaseModel):
    incident_id: str
    job_id: str
    detected_at_seconds: float
    confidence: float = Field(ge=0, le=1)
    status: Literal["detected", "acknowledged"]
    created_at_utc: str


class Result(BaseModel):
    job_id: str
    duration_seconds: float
    frame_width: int
    frame_height: int
    model_version: str | None
    analysis_mode: Literal["cached", "on_demand"]
    media_url: str
    predictions: list[Prediction]
    poses: list[Pose]
    incidents: list[Incident]
    metrics: dict[str, float | int | None]
    reports: dict[str, str]
