"""Typed API records using snake_case fields and source-time seconds."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, FiniteFloat

# Preserve finite source-model joint scores; they are not fall probabilities.
KeypointScore = FiniteFloat


JobState = Literal["queued", "running", "completed", "failed", "cancelled"]
# Per-source person ID from the engine's tracker (1, 2, ...). Optional so results
# stored before multi-person tracking still validate.
TrackId = int | None


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorBody(BaseModel):
    error: ErrorDetail


class Job(BaseModel):
    job_id: str
    state: JobState
    progress: float | None = Field(ge=0, le=1)
    source_kind: Literal["upload"]
    created_at_utc: str
    model_version: str | None
    result_url: str | None
    error: ErrorDetail | None


class Prediction(BaseModel):
    track_id: TrackId = Field(default=None, ge=1)
    timestamp_seconds: FiniteFloat = Field(ge=0)
    fall_probability: FiniteFloat = Field(ge=0, le=1)
    window_start_seconds: FiniteFloat | None = None
    source_pose_count: int | None = Field(default=None, ge=0)
    inference_ms: FiniteFloat | None = Field(default=None, ge=0)
    urgency: FiniteFloat | None = None
    reliability: FiniteFloat | None = None


class Pose(BaseModel):
    track_id: TrackId = Field(default=None, ge=1)
    timestamp_seconds: FiniteFloat = Field(ge=0)
    bbox_xyxy: list[FiniteFloat] = Field(min_length=4, max_length=4)
    keypoints: list[tuple[FiniteFloat, FiniteFloat, KeypointScore]] = Field(min_length=17, max_length=17)


class Incident(BaseModel):
    incident_id: str
    job_id: str
    track_id: TrackId = Field(default=None, ge=1)
    clip_id: str | None = None  # GET /clips/{clip_id}; None when no clip was kept
    detected_at_seconds: float
    confidence: float = Field(ge=0, le=1)
    status: Literal["detected", "acknowledged"]
    created_at_utc: str


class Result(BaseModel):
    job_id: str
    duration_seconds: FiniteFloat = Field(ge=0)
    frame_width: int = Field(gt=0)
    frame_height: int = Field(gt=0)
    model_version: str | None
    analysis_mode: Literal["cached", "on_demand"]
    media_url: str
    predictions: list[Prediction]
    poses: list[Pose]
    incidents: list[Incident]
    metrics: dict[str, FiniteFloat | int | None]
    reports: dict[str, str]


class LiveSession(BaseModel):
    session_id: str
    created_at_utc: str
    model_version: str


class LiveIncident(BaseModel):
    incident_id: str
    session_id: str
    track_id: TrackId = Field(default=None, ge=1)
    clip_id: str | None = None  # pending until the second after the fall has been captured
    detected_at_seconds: FiniteFloat = Field(ge=0)
    confidence: FiniteFloat = Field(ge=0, le=1)
    created_at_utc: str


class LivePerson(BaseModel):
    """One tracked person in the analyzed frame, with their own temporal state."""
    track_id: int = Field(ge=1)
    pose: Pose
    prediction: Prediction | None
    status: Literal['warming_up', 'monitoring']
    coverage_seconds: FiniteFloat = Field(ge=0)
    pose_count: int = Field(ge=0)
    incident_latched: bool


class LiveFrame(BaseModel):
    session_id: str
    model_version: str
    timestamp_seconds: FiniteFloat = Field(ge=0)
    frame_width: int = Field(gt=0)
    frame_height: int = Field(gt=0)
    people: list[LivePerson]
    status: Literal['no_person', 'warming_up', 'monitoring']
    track_resets: int = Field(ge=0)
    frames_processed: int = Field(ge=0)
    processed_fps: FiniteFloat = Field(ge=0)
    processing_ms: FiniteFloat = Field(ge=0)
    incidents: list[LiveIncident]
    incident_latched: bool


class LiveHistory(LiveSession):
    state: Literal['active', 'stopped', 'failed']
    frames_processed: int = Field(ge=0)
    ended_at_utc: str | None
    error_message: str | None
    incidents: list[LiveIncident]


class LiveHistoryResponse(BaseModel):
    sessions: list[LiveHistory]


class Clip(BaseModel):
    """A short video around one detected fall.

    ``detected_at_seconds`` is on the source clock (video time for uploads,
    camera-session time for live). The clip covers
    [clip_start_seconds, clip_start_seconds + duration_seconds] on that same clock.
    """
    clip_id: str
    source_kind: Literal['upload', 'live']
    source_id: str
    track_id: TrackId = Field(default=None, ge=1)
    status: Literal['pending', 'ready', 'failed']
    detected_at_seconds: FiniteFloat = Field(ge=0)
    confidence: FiniteFloat = Field(ge=0, le=1)
    clip_start_seconds: FiniteFloat | None = None
    duration_seconds: FiniteFloat | None = None
    created_at_utc: str
    expires_at_utc: str
    size_bytes: int | None = None
    media_type: str | None = None
    video_url: str | None = None
    error_message: str | None = None


class ClipList(BaseModel):
    clips: list[Clip]
    storage_used_bytes: int = Field(ge=0)
    storage_cap_bytes: int = Field(gt=0)
    retention_seconds: FiniteFloat = Field(gt=0)
