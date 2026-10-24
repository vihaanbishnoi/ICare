/**
 * Type definitions mirroring src/icare/api/schemas.py — do not invent fields.
 * Source of truth: src/icare/api/schemas.py
 */

type JobState = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

interface ErrorDetail {
  code: string;
  message: string;
}

export interface Job {
  job_id: string;
  state: JobState;
  progress: number | null;
  source_kind: 'upload';
  created_at_utc: string;
  model_version: string | null;
  result_url: string | null;
  error: ErrorDetail | null;
}

/** Per-source person ID from the tracker; null in results stored before tracking. */
export type TrackId = number | null | undefined;

/** Prediction from engine — timestamp_seconds, fall_probability in [0,1] */
export interface Prediction {
  track_id?: TrackId;
  timestamp_seconds: number;
  fall_probability: number;
  window_start_seconds?: number | null;
  source_pose_count?: number | null;
  inference_ms?: number | null;
  urgency?: number | null;
  reliability?: number | null;
}

/** 17 COCO keypoints [x, y, confidence]. Coordinates relative to frame_width/frame_height. */
export interface Pose {
  track_id?: TrackId;
  /** Enrolled resident's name once their face was matched; null while unknown. */
  identity?: string | null;
  timestamp_seconds: number;
  bbox_xyxy: [number, number, number, number];
  keypoints: [number, number, number][];  // 17 entries
}

export interface Incident {
  incident_id: string;
  job_id: string;
  track_id?: TrackId;
  identity?: string | null;
  /** Fall clip for GET /clips/{clip_id}; absent when none was kept. */
  clip_id?: string | null;
  detected_at_seconds: number;
  confidence: number;
  status: 'detected' | 'acknowledged';
  created_at_utc: string;
}

export type BehaviourType = 'pacing' | 'prolonged_inactivity' | 'long_lie';

/**
 * One unusual-behaviour interval for one tracked person. Times are on the source clock;
 * end_seconds is null while ongoing. end_reason: the behaviour stopped ('resolved'),
 * the person left view ('person_lost') or the video/camera ended ('source_ended').
 */
export interface BehaviourEvent {
  event_id: string;
  source_kind: 'upload' | 'live';
  source_id: string;
  track_id?: TrackId;
  identity?: string | null;
  event_type: BehaviourType;
  severity: 'attention' | 'urgent';
  start_seconds: number;
  detected_at_seconds: number;
  end_seconds: number | null;
  end_reason: 'resolved' | 'person_lost' | 'source_ended' | null;
  evidence: Record<string, number>;
  created_at_utc: string;
}

/** One person's progress towards each behaviour event. */
export interface BehaviourState {
  evidence: 'good' | 'insufficient';
  still_seconds: number;
  pacing_turns: number;
  down_after_fall_seconds: number | null;
  active_events: BehaviourType[];
}

export interface Result {
  job_id: string;
  duration_seconds: number;
  frame_width: number;
  frame_height: number;
  model_version: string | null;
  analysis_mode: 'cached' | 'on_demand';
  media_url: string;
  predictions: Prediction[];
  poses: Pose[];
  incidents: Incident[];
  behaviour_events?: BehaviourEvent[];
  metrics: Record<string, number | null>;
  reports: Record<string, string>;
}

export interface LiveIncident {
  incident_id: string; session_id: string; track_id?: TrackId; identity?: string | null; clip_id?: string | null; detected_at_seconds: number;
  confidence: number; created_at_utc: string;
}

export interface LiveSession {
  session_id: string; created_at_utc: string; model_version: string;
}

export interface LiveHistory extends LiveSession {
  state: 'active' | 'stopped' | 'failed'; frames_processed: number;
  ended_at_utc: string | null; error_message: string | null; incidents: LiveIncident[];
  behaviour_events?: BehaviourEvent[];
}

/** One tracked person in an analyzed camera frame, with independent temporal state. */
export interface LivePerson {
  track_id: number; identity?: string | null; pose: Pose; prediction: Prediction | null;
  status: 'warming_up' | 'monitoring'; coverage_seconds: number; pose_count: number;
  incident_latched: boolean;
  behaviour?: BehaviourState | null;
}

export interface LiveFrame {
  session_id: string; model_version: string; timestamp_seconds: number;
  frame_width: number; frame_height: number; people: LivePerson[];
  status: 'no_person' | 'warming_up' | 'monitoring';
  track_resets: number; frames_processed: number; processed_fps: number; processing_ms: number;
  incidents: LiveIncident[]; incident_latched: boolean;
  /** Behaviour events opened or ended by this frame. */
  behaviour_events?: BehaviourEvent[];
}

/**
 * A ~5 s video of one detected fall. Times are on the source clock: video time for
 * uploads, camera-session time for live. The clip covers
 * [clip_start_seconds, clip_start_seconds + duration_seconds].
 */
export interface Clip {
  clip_id: string;
  source_kind: 'upload' | 'live';
  source_id: string;
  track_id?: TrackId;
  identity?: string | null;
  /** The room the camera or upload was started for, if any. */
  room?: string | null;
  status: 'pending' | 'ready' | 'failed';
  detected_at_seconds: number;
  confidence: number;
  clip_start_seconds: number | null;
  duration_seconds: number | null;
  created_at_utc: string;
  expires_at_utc: string;
  size_bytes: number | null;
  media_type: string | null;
  video_url: string | null;
  /** Still of where the fall began, kept as long as the clip. */
  snapshot_url?: string | null;
  error_message: string | null;
}

export interface ClipList {
  clips: Clip[];
  storage_used_bytes: number;
  storage_cap_bytes: number;
  retention_seconds: number;
}

/** A resident enrolled for face matching. Photos are not stored, only face measurements. */
export interface Resident {
  resident_id: string;
  name: string;
  room: string | null;
  photo_count: number;
  created_at_utc: string;
}

export interface ResidentList {
  residents: Resident[];
  face_models_ready: boolean;
}

export interface DailyLogEntry {
  log_id: string;
  timestamp: string;
  resident_id: string;
  resident_name: string;
  room: string;
  wing: string;
  event_type: string;
  confidence: number;
  status: string;
  response_time_seconds: number | null;
  attended_by: string | null;
  staff_notes: string | null;
}

export interface DailyLogsResponse {
  total_logs: number;
  logs: DailyLogEntry[];
}

export interface IncidentStats {
  total_events: number;
  confirmed_falls: number;
  near_falls: number;
  avg_response_time_seconds: number;
}

export interface HighRiskResident {
  resident_name: string;
  room: string;
  wing: string;
  risk_level: string;
  incident_summary: string;
  action_plan: string;
}

export interface DailySummaryStructured {
  executive_summary: string;
  incident_stats: IncidentStats;
  high_risk_residents: HighRiskResident[];
  key_observations: string[];
  shift_handoff_recommendations: string[];
  shift_handoff_notes: string;
}

export interface DailySummaryResponse {
  status: 'success' | 'fallback' | 'empty';
  model: string;
  summary: string;
  structured_summary?: DailySummaryStructured | null;
  log_count: number;
  generated_at_utc: string;
  ollama_connected: boolean;
  notice?: string | null;
}

export interface CaretakerEmailRecord {
  email_id: string;
  summary_id?: string | null;
  recipient_name: string;
  recipient_email: string;
  recipient_role: string;
  subject: string;
  body_preview?: string | null;
  body_text?: string | null;
  sent_at_utc: string;
  status: string;
}

export interface CaretakersListResponse {
  total_emails: number;
  emails: CaretakerEmailRecord[];
}

export interface SchedulerStatusResponse {
  scheduled_time: string;
  target_hour: number;
  is_active: boolean;
  next_scheduled_run: string;
  last_run_at?: string | null;
  last_run_status?: string | null;
  last_run_email_count: number;
  latest_saved_summary?: {
    summary_id: string;
    date_str: string;
    generated_at_utc: string;
    model: string;
    status: string;
    sent_email_count: number;
  } | null;
  caretakers: { name: string; email: string; role: string }[];
}

export interface Trigger10pmResponse {
  status: string;
  summary_id: string;
  date_str: string;
  generated_at_utc: string;
  model: string;
  summary: DailySummaryResponse;
  emails_dispatched: number;
  emails: CaretakerEmailRecord[];
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatResponse {
  question: string;
  reply: string;
  model: string;
  grounded: boolean;
  notice?: string | null;
  sources: string[];
}




/**
 * One fall's position in a fixed camera's image, normalised to 0..1 (x of width, y of height).
 * `onset` is where the person was when the fall began, `landing` where they ended up.
 * `onset_estimated` is false when no clear descent was found and onset repeats the landing point.
 */
export interface FallLocation {
  fall_id: string;
  source_kind: 'upload' | 'live';
  track_id?: TrackId;
  detected_at_seconds: number;
  onset_seconds: number | null;
  created_at_utc: string;
  confidence: number;
  onset_x: number; onset_y: number;
  landing_x: number; landing_y: number;
  body_width: number;
  onset_estimated: boolean;
  frame_width: number; frame_height: number;
}

/** Every recorded fall position in one room; shared by everyone using the server. */
export interface DangerZone {
  room: string;
  frame_width: number | null;
  frame_height: number | null;
  photo_url: string | null;
  total_falls: number;
  generated_at_utc: string;
  falls: FallLocation[];
}

export interface RoomSummary {
  room: string;
  fall_count: number;
  last_fall_utc: string | null;
  has_photo: boolean;
}
