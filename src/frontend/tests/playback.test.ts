import test from 'node:test';
import assert from 'node:assert/strict';
import { hasRecordedIncident, poseAtTime, predictionAtTime } from '../src/lib/playback.ts';
import type { Incident, Pose, Prediction } from '../src/types.ts';

const predictions: Prediction[] = [
  { timestamp_seconds: 2, fall_probability: 0.1 },
  { timestamp_seconds: 3, fall_probability: 0.9 },
];

test('playback never displays future confidence', () => {
  assert.equal(predictionAtTime(predictions, 1.9), null);
  assert.equal(predictionAtTime(predictions, 2.9)?.fall_probability, 0.1);
  assert.equal(predictionAtTime(predictions, 3)?.fall_probability, 0.9);
});

test('seeking backwards and stale data do not reuse later predictions', () => {
  assert.equal(predictionAtTime(predictions, 5), null);
  assert.equal(predictionAtTime(predictions, 2.1)?.fall_probability, 0.1);
  assert.equal(predictionAtTime(predictions, Number.NaN), null);
});

test('missing-person gaps clear the skeleton overlay', () => {
  const pose: Pose = { timestamp_seconds: 2, bbox_xyxy: [0, 0, 10, 10], keypoints: [] };
  assert.equal(poseAtTime([pose], 2.1), pose);
  assert.equal(poseAtTime([pose], 2.6), null);
});

test('a recorded incident has no invented four-second recovery', () => {
  const incident: Incident = { incident_id: 'fixture', job_id: 'fixture', detected_at_seconds: 3,
    confidence: 0.9, status: 'detected', created_at_utc: '2026-10-10T00:00:00Z' };
  assert.equal(hasRecordedIncident([incident], 2.9), false);
  assert.equal(hasRecordedIncident([incident], 9), true);
});
