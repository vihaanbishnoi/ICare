"""Behaviour event rules on synthetic people. These check the rules, not real-world accuracy."""
import math
import unittest

import numpy as np

from icare.inference.behaviour import BehaviourMonitor, BehaviourSettings
from tests.helpers import person, times

FAST = BehaviourSettings(inactivity_seconds=20, long_lie_seconds=10)


def record(pose, track_id=1, jitter=0.0, rng=None):
    keypoints = np.asarray(pose.keypoints, dtype=np.float64).copy()
    if jitter:
        keypoints[:, :2] += rng.normal(0, jitter, size=(17, 2))
    return {"track_id": track_id, "timestamp_seconds": pose.timestamp_seconds,
            "bbox_xyxy": [float(v) for v in pose.bbox], "keypoints": keypoints.tolist()}


def run(monitor, records):
    events = []
    for item in records:
        for event in monitor.observe(item):
            if event not in events:
                events.append(event)
    for event in monitor.finish():
        if event not in events:
            events.append(event)
    return events


def walk(xs_at, seconds, jitter=0.0, track_id=1, seed=0, **kwargs):
    rng = np.random.default_rng(seed)
    return [record(person(t, xs_at(t), 300, **kwargs), track_id, jitter, rng) for t in times(seconds)]


def pace(t, left=100.0, right=600.0, leg_seconds=5.0):
    """Triangle wave: walk left→right→left at a steady pace (body height 180 px)."""
    phase = (t / leg_seconds) % 2
    return left + (right - left) * (phase if phase < 1 else 2 - phase)


class PacingTests(unittest.TestCase):
    def test_repeated_back_and_forth_is_one_pacing_event(self):
        events = run(BehaviourMonitor(FAST), walk(pace, 40, jitter=2))
        pacing = [e for e in events if e["event_type"] == "pacing"]
        self.assertEqual(len(pacing), 1)
        event = pacing[0]
        # Fourth turn happens at 20 s and is confirmed after walking back 0.5 body lengths.
        self.assertTrue(20 <= event["detected_at_seconds"] <= 22, event)
        self.assertLessEqual(event["start_seconds"], 1.0)
        self.assertGreaterEqual(event["evidence"]["turns"], 4)
        self.assertEqual(event["end_reason"], "source_ended")

    def test_walk_through_and_single_return_do_not_trigger(self):
        through = walk(lambda t: 50 + 25 * t, 30)
        there_and_back = walk(lambda t: pace(t, leg_seconds=12), 30)  # two turns only
        for records in (through, there_and_back):
            self.assertEqual(run(BehaviourMonitor(FAST), records), [])

    def test_shifting_weight_in_place_does_not_trigger(self):
        sway = walk(lambda t: 300 + 60 * math.sin(t * 2), 60, jitter=2)
        self.assertEqual([e for e in run(BehaviourMonitor(FAST), sway) if e["event_type"] == "pacing"], [])

    def test_pacing_ends_after_walking_stops(self):
        records = walk(lambda t: pace(t) if t < 30 else pace(30), 80)
        pacing = [e for e in run(BehaviourMonitor(FAST), records) if e["event_type"] == "pacing"]
        self.assertEqual(len(pacing), 1)
        self.assertEqual(pacing[0]["end_reason"], "resolved")
        self.assertLess(pacing[0]["end_seconds"], 31)

    def test_people_are_independent(self):
        records = sorted(walk(pace, 40, track_id=1) + walk(lambda t: 900.0, 40, track_id=2, jitter=3, seed=1),
                         key=lambda r: (r["timestamp_seconds"], r["track_id"]))
        events = run(BehaviourMonitor(BehaviourSettings(inactivity_seconds=1000)), records)
        self.assertEqual([(e["track_id"], e["event_type"]) for e in events], [(1, "pacing")])


class InactivityTests(unittest.TestCase):
    def test_motionless_person_triggers_once_and_ends_on_movement(self):
        records = walk(lambda t: 300.0 if t < 40 else 300 + 40 * (t - 40), 50, jitter=1.5)
        events = run(BehaviourMonitor(FAST), records)
        self.assertEqual([e["event_type"] for e in events], ["prolonged_inactivity"])
        event = events[0]
        self.assertTrue(20 <= event["detected_at_seconds"] <= 21, event)
        self.assertEqual(event["end_reason"], "resolved")
        self.assertTrue(40 <= event["end_seconds"] <= 41, event)

    def test_natural_sway_is_not_inactivity(self):
        # Swaying about 0.1 body lengths, like the standing clips measured with YOLO26n-pose.
        records = walk(lambda t: 300 + 12 * math.sin(t * 1.5), 60, jitter=1.5)
        self.assertEqual(run(BehaviourMonitor(FAST), records), [])

    def test_single_frame_jitter_does_not_reset_the_clock(self):
        rng = np.random.default_rng(3)
        records = []
        for t in times(30):
            item = record(person(t, 300, 300), 1, 1.0, rng)
            if int(t * 6) % 20 == 0:  # one bad joint estimate every ~3 s
                item["keypoints"][9][0] += 80
            records.append(item)
        events = run(BehaviourMonitor(FAST), records)
        self.assertEqual([e["event_type"] for e in events], ["prolonged_inactivity"])

    def test_poor_visibility_is_insufficient_evidence(self):
        monitor = BehaviourMonitor(FAST)
        records = [record(person(t, 300, 300, confidence=0.3)) for t in times(60)]
        self.assertEqual(run(monitor, records), [])
        monitor.observe(records[-1] | {"timestamp_seconds": 61.0})
        self.assertEqual(monitor.state(1)["evidence"], "insufficient")

    def test_gap_restarts_the_stillness_clock(self):
        records = [r for r in walk(lambda t: 300.0, 30) if not 12 <= r["timestamp_seconds"] < 13.5]
        self.assertEqual(run(BehaviourMonitor(FAST), records), [])

    def test_person_who_leaves_ends_the_event(self):
        monitor = BehaviourMonitor(FAST)
        events = run(monitor, walk(lambda t: 300.0, 25, track_id=1)
                     + [record(person(t, 900, 300), 2) for t in times(30) if t >= 28])
        self.assertEqual([(e["event_type"], e["end_reason"]) for e in events], [("prolonged_inactivity", "person_lost")])


class LongLieTests(unittest.TestCase):
    def fall_then(self, lying_until, seconds=30):
        monitor = BehaviourMonitor(FAST)
        events = []
        for t in times(seconds):
            lying = 0.0 if t < 3 else 1.0 if t < lying_until else 0.0
            events += monitor.observe(record(person(t, 300, 300, lying=lying)))
            if abs(t - 4.0) < 1e-6:
                monitor.note_fall(1, t)
        unique = []
        for event in events + monitor.finish():
            if event not in unique:
                unique.append(event)
        return unique

    def test_still_down_after_fall_escalates(self):
        events = self.fall_then(lying_until=100)
        long_lie = [e for e in events if e["event_type"] == "long_lie"]
        self.assertEqual(len(long_lie), 1)
        self.assertEqual(long_lie[0]["severity"], "urgent")
        self.assertAlmostEqual(long_lie[0]["start_seconds"], 4.0)
        self.assertTrue(14 <= long_lie[0]["detected_at_seconds"] <= 15)
        # Lying still after a fall is reported as a long lie, not also as inactivity.
        self.assertNotIn("prolonged_inactivity", [e["event_type"] for e in events])

    def test_getting_up_before_the_limit_does_not_escalate(self):
        # Stops before standing still long enough to count as inactivity.
        self.assertEqual(self.fall_then(lying_until=9, seconds=25), [])

    def test_getting_up_ends_a_long_lie(self):
        events = self.fall_then(lying_until=20)
        self.assertEqual([(e["event_type"], e["end_reason"]) for e in events], [("long_lie", "resolved")])
        self.assertAlmostEqual(events[0]["end_seconds"], 20.0, places=4)

    def test_reclining_after_a_fall_alert_is_not_escalated(self):
        # Torso at 45 degrees (e.g. slumped in a chair after a possibly false alert): not lying.
        monitor = BehaviourMonitor(BehaviourSettings(inactivity_seconds=1000, long_lie_seconds=10))
        monitor.observe(record(person(0.0, 300, 300)))
        monitor.note_fall(1, 0.0)
        self.assertEqual(run(monitor, [record(person(t, 300, 300, lying=0.5)) for t in times(40)[1:]]), [])

    def test_lying_without_a_recorded_fall_is_not_a_long_lie(self):
        monitor = BehaviourMonitor(BehaviourSettings(inactivity_seconds=1000, long_lie_seconds=10))
        self.assertEqual(run(monitor, [record(person(t, 300, 300, lying=1.0)) for t in times(60)]), [])


class SettingsTests(unittest.TestCase):
    def test_invalid_settings_are_rejected(self):
        with self.assertRaises(ValueError):
            BehaviourSettings(inactivity_seconds=0)
        with self.assertRaises(ValueError):
            BehaviourSettings(pacing_reversals=1)


if __name__ == "__main__":
    unittest.main()
