import type { Incident, Pose, Prediction } from '../types.ts';

/** Recorded-video lookup only; do not show a prediction before it was emitted. */
export function predictionAtTime(records: Prediction[], time: number, maxAge = 1.5): Prediction | null {
  if (!Number.isFinite(time)) return null;
  let latest: Prediction | null = null;
  for (const record of records) {
    if (record.timestamp_seconds <= time && (!latest || record.timestamp_seconds > latest.timestamp_seconds)) {
      latest = record;
    }
  }
  return latest && time - latest.timestamp_seconds <= maxAge ? latest : null;
}

/** Nearest sampled pose; blank the overlay across missing-person gaps. */
export function poseAtTime(records: Pose[], time: number, tolerance = 0.25): Pose | null {
  if (!Number.isFinite(time)) return null;
  let nearest: Pose | null = null;
  let distance = tolerance;
  for (const pose of records) {
    const delta = Math.abs(pose.timestamp_seconds - time);
    if (delta <= distance) { nearest = pose; distance = delta; }
  }
  return nearest;
}

/** An incident has no inferred recovery/end timestamp. */
export function hasRecordedIncident(incidents: Incident[], time: number): boolean {
  return incidents.some(incident => incident.detected_at_seconds <= time);
}
