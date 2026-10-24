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
  timestamp_seconds: number;
  bbox_xyxy: [number, number, number, number];
  keypoints: [number, number, number][];  // 17 entries
}

export interface Incident {
  incident_id: string;
  job_id: string;
  track_id?: TrackId;
  detected_at_seconds: number;
  confidence: number;
  status: 'detected' | 'acknowledged';
  created_at_utc: string;
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
  metrics: Record<string, number | null>;
  reports: Record<string, string>;
}

export interface LiveIncident {
  incident_id: string; session_id: string; track_id?: TrackId; detected_at_seconds: number;
  confidence: number; created_at_utc: string;
}

export interface LiveSession {
  session_id: string; created_at_utc: string; model_version: string;
}

export interface LiveHistory extends LiveSession {
  state: 'active' | 'stopped' | 'failed'; frames_processed: number;
  ended_at_utc: string | null; error_message: string | null; incidents: LiveIncident[];
}

/** One tracked person in an analyzed camera frame, with independent temporal state. */
export interface LivePerson {
  track_id: number; pose: Pose; prediction: Prediction | null;
  status: 'warming_up' | 'monitoring'; coverage_seconds: number; pose_count: number;
  incident_latched: boolean;
}

export interface LiveFrame {
  session_id: string; model_version: string; timestamp_seconds: number;
  frame_width: number; frame_height: number; people: LivePerson[];
  status: 'no_person' | 'warming_up' | 'monitoring';
  track_resets: number; frames_processed: number; processed_fps: number; processing_ms: number;
  incidents: LiveIncident[]; incident_latched: boolean;
}
