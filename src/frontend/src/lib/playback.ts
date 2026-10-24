import type { Incident, Pose, Prediction, TrackId } from '../types.ts';
import { byPerson, personKey } from './people.ts';

/** Each person's latest prediction at ``time``; never one emitted after it. */
export function predictionsAtTime(records: Prediction[], time: number, maxAge = 1.5): Map<number, Prediction> {
  const latest = new Map<number, Prediction>();
  if (!Number.isFinite(time)) return latest;
  for (const [key, group] of byPerson(records)) {
    let best: Prediction | null = null;
    for (const record of group) {
      if (record.timestamp_seconds <= time && (!best || record.timestamp_seconds > best.timestamp_seconds)) best = record;
    }
    if (best && time - best.timestamp_seconds <= maxAge) latest.set(key, best);
  }
  return latest;
}

/** Each person's nearest sampled pose; nobody is drawn across a missing-person gap. */
export function posesAtTime(records: Pose[], time: number, tolerance = 0.25): Pose[] {
  if (!Number.isFinite(time)) return [];
  const nearest: Pose[] = [];
  for (const group of byPerson(records).values()) {
    let best: Pose | null = null;
    let distance = tolerance;
    for (const pose of group) {
      const delta = Math.abs(pose.timestamp_seconds - time);
      if (delta <= distance) { best = pose; distance = delta; }
    }
    if (best) nearest.push(best);
  }
  return nearest;
}

/** A person's incident has no inferred recovery/end timestamp. */
export function hasRecordedIncident(incidents: Incident[], time: number, trackId: TrackId): boolean {
  return incidents.some(incident => personKey(incident.track_id) === personKey(trackId) && incident.detected_at_seconds <= time);
}
