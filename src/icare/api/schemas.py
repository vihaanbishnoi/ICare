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
    room: str | None = None  # the room the camera or upload was started for, if any
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
    snapshot_url: str | None = None  # still of where the fall began, kept as long as the clip
    error_message: str | None = None


class ClipList(BaseModel):
    clips: list[Clip]
    storage_used_bytes: int = Field(ge=0)
    storage_cap_bytes: int = Field(gt=0)
    retention_seconds: FiniteFloat = Field(gt=0)


class DailyLogEntry(BaseModel):
    log_id: str
    timestamp: str
    resident_id: str
    resident_name: str
    room: str
    wing: str
    event_type: str
    confidence: FiniteFloat = Field(ge=0, le=1)
    status: str
    response_time_seconds: int | None = None
    attended_by: str | None = None
    staff_notes: str | None = None


class DailyLogsResponse(BaseModel):
    total_logs: int
    logs: list[DailyLogEntry]


class IncidentStats(BaseModel):
    total_events: int = 0
    confirmed_falls: int = 0
    near_falls: int = 0
    avg_response_time_seconds: float = 0.0


class HighRiskResident(BaseModel):
    resident_name: str
    room: str
    wing: str
    risk_level: str
    incident_summary: str
    action_plan: str


class DailySummaryStructured(BaseModel):
    executive_summary: str
    incident_stats: IncidentStats
    high_risk_residents: list[HighRiskResident] = []
    key_observations: list[str] = []
    shift_handoff_recommendations: list[str] = []
    shift_handoff_notes: str = ""


class DailySummaryResponse(BaseModel):
    status: Literal['success', 'fallback', 'empty']
    model: str
    summary: str
    structured_summary: DailySummaryStructured | None = None
    log_count: int
    generated_at_utc: str
    ollama_connected: bool
    notice: str | None = None


class CaretakerEmailRecord(BaseModel):
    email_id: str
    summary_id: str | None = None
    recipient_name: str
    recipient_email: str
    recipient_role: str
    subject: str
    body_preview: str | None = None
    body_text: str | None = None
    sent_at_utc: str
    status: str


class CaretakersListResponse(BaseModel):
    total_emails: int
    emails: list[CaretakerEmailRecord]


class SchedulerStatusResponse(BaseModel):
    scheduled_time: str
    target_hour: int
    is_active: bool
    next_scheduled_run: str
    last_run_at: str | None = None
    last_run_status: str | None = None
    last_run_email_count: int = 0
    latest_saved_summary: dict[str, Any] | None = None
    caretakers: list[dict[str, str]]


class Trigger10pmResponse(BaseModel):
    status: str
    summary_id: str
    date_str: str
    generated_at_utc: str
    model: str
    summary: dict[str, Any]
    emails_dispatched: int
    emails: list[dict[str, Any]]


class ChatMessage(BaseModel):
    role: Literal['user', 'assistant', 'system']
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    model: str = "llama3.2:1b"


class ChatResponse(BaseModel):
    question: str
    reply: str
    model: str
    grounded: bool
    notice: str | None = None
    sources: list[str] = []


class FallLocation(BaseModel):
    """One fall's position in a fixed camera's image, normalised to 0..1 (x of width, y of height).

    ``onset`` is where the person was when the fall began; ``landing`` is where they ended up.
    ``onset_estimated`` is false when no clear descent was found and onset repeats the landing point.
    """
    fall_id: str
    source_kind: Literal['upload', 'live']
    track_id: TrackId = Field(default=None, ge=1)
    detected_at_seconds: FiniteFloat = Field(ge=0)
    onset_seconds: FiniteFloat | None = None
    created_at_utc: str
    confidence: FiniteFloat = Field(ge=0, le=1)
    onset_x: FiniteFloat = Field(ge=0, le=1)
    onset_y: FiniteFloat = Field(ge=0, le=1)
    landing_x: FiniteFloat = Field(ge=0, le=1)
    landing_y: FiniteFloat = Field(ge=0, le=1)
    body_width: FiniteFloat = Field(ge=0, le=1)
    onset_estimated: bool
    frame_width: int = Field(gt=0)
    frame_height: int = Field(gt=0)


class DangerZone(BaseModel):
    room: str
    frame_width: int | None
    frame_height: int | None
    photo_url: str | None
    total_falls: int = Field(ge=0)
    generated_at_utc: str
    falls: list[FallLocation]


class RoomSummary(BaseModel):
    room: str
    fall_count: int = Field(ge=0)
    last_fall_utc: str | None
    has_photo: bool


class RoomList(BaseModel):
    rooms: list[RoomSummary]
