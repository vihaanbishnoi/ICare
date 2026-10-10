/**
 * Type definitions mirroring api/schemas.py — do not invent fields.
 * Source of truth: docs/interfaces/api.md
 */

export type JobState = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface ErrorDetail {
  code: string;
  message: string;
}

export interface Example {
  example_id: string;
  title: string;
  expected_outcome: 'fall' | 'no_fall';
  video_url: string;
  duration_seconds: number;
  analysis_mode: 'cached' | 'on_demand';
  model_version: string | null;
  provenance: string;
}

export interface ExamplesResponse {
  examples: Example[];
}

export interface Job {
  job_id: string;
  state: JobState;
  progress: number | null;
  source_kind: 'example' | 'upload';
  created_at_utc: string;
  model_version: string | null;
  result_url: string | null;
  error: ErrorDetail | null;
}

/** Prediction from engine — timestamp_seconds, fall_probability in [0,1] */
export interface Prediction {
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
  timestamp_seconds: number;
  bbox_xyxy: [number, number, number, number];
  keypoints: [number, number, number][];  // 17 entries
}

export interface Incident {
  incident_id: string;
  job_id: string;
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
