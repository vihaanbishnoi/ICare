"""Per-person engine windows and per-person incidents, end to end through FrameSession.

The stand-in classifier only sees one window at a time, so these tests prove
isolation, scheduling and event logic. They do not measure fall accuracy.
"""
import unittest
from pathlib import Path

import numpy as np

from icare.api.incidents import IncidentTracker, PersonIncidents
from icare.inference.engine import EngineConfig, FrameSession, PoseC3DEngine
from tests.helpers import DescentClassifier, ScriptedPeople, person, times

FRAME = np.zeros((360, 400, 3), dtype=np.uint8)


def fall_progress(t, start, duration=0.6):
    return min(max((t - start) / duration, 0.0), 1.0)


def fall_then_get_up(t, start, lie_seconds=3.0, get_up_seconds=1.5):
    """0 standing .. 1 lying: fall in 0.6 s, lie still, then get up gradually."""
    rise = t - (start + 0.6 + lie_seconds)
    return fall_progress(t, start) if rise <= 0 else max(0.0, 1.0 - rise / get_up_seconds)


def run(script, seconds, *, confirmations=1, max_per_frame=None, drain=True, **config):
    """Run a scripted scene; returns predictions, incidents and the session."""
    engine = PoseC3DEngine(EngineConfig(model_path=Path("unused.onnx"), **config),
                           ScriptedPeople(script), DescentClassifier())
    session = FrameSession(engine, max_predictions_per_frame=max_per_frame)
    book, predictions, incidents = PersonIncidents(confirmations), [], []

    def observe(prediction):
        predictions.append(prediction)
        if book.observe(prediction["track_id"], prediction["fall_probability"]):
            incidents.append((prediction["track_id"], prediction["timestamp_seconds"]))

    for t in times(seconds):
        record = session.process_frame(FRAME, t)
        for prediction in record["predictions"]:
            observe(prediction)
    if drain:  # recorded videos only; live sessions never drain
        for prediction in session.finish():
            observe(prediction)
    return predictions, incidents, session


def first_track(predictions, track_id):
    return [p for p in predictions if p["track_id"] == track_id]


class MultiPersonEngineTests(unittest.TestCase):
    def test_one_person_falls_while_four_others_stand(self):
        def scene(t):
            return [person(t, 20, 60, w=30, h=90, lying=fall_progress(t, 4.0))] + \
                   [person(t, 80 + 70 * i, 60, w=30, h=90) for i in range(4)]
        predictions, incidents, _ = run(scene, 8)
        self.assertEqual([tid for tid, _ in incidents], [1])
        for tid in range(2, 6):
            self.assertLess(max(p["fall_probability"] for p in first_track(predictions, tid)), 0.5)

    def test_simultaneous_falls_are_separate_incidents(self):
        def scene(t):
            return [person(t, 20, 60, w=30, h=90, lying=fall_progress(t, 4.0)),
                    person(t, 150, 60, w=30, h=90),
                    person(t, 280, 60, w=30, h=90, lying=fall_progress(t, 4.0))]
        _, incidents, _ = run(scene, 8)
        self.assertEqual(sorted(tid for tid, _ in incidents), [1, 3])

    def test_consecutive_falls_by_different_people_are_both_recorded(self):
        def scene(t):
            return [person(t, 20, 60, w=30, h=90, lying=fall_progress(t, 3.0)),
                    person(t, 200, 60, w=30, h=90, lying=fall_progress(t, 5.0))]
        predictions, incidents, _ = run(scene, 9)
        self.assertEqual([tid for tid, _ in incidents], [1, 2])
        # Root cause demonstrated: the old single, shared tracker misses the second fall.
        shared = IncidentTracker()
        ordered = sorted(predictions, key=lambda p: (p["timestamp_seconds"], p["track_id"]))
        self.assertEqual(sum(shared.observe(p["fall_probability"]) for p in ordered), 1)

    def test_rapid_falls_by_four_people(self):
        def scene(t):
            return [person(t, 15 + 95 * i, 60, w=30, h=90, lying=fall_progress(t, 3.0 + 0.3 * i)) for i in range(4)]
        _, incidents, _ = run(scene, 8)
        self.assertEqual(sorted(tid for tid, _ in incidents), [1, 2, 3, 4])

    def test_people_already_lying_or_standing_still_raise_nothing(self):
        def scene(t):
            return [person(t, 20, 60, w=30, h=90, lying=1.0), person(t, 200, 60, w=30, h=90)]
        _, incidents, _ = run(scene, 8)
        self.assertEqual(incidents, [])

    def test_fallen_person_moving_does_not_realert_until_rearmed(self):
        def scene(t):
            # Falls at 2.5 s, shuffles on the floor, gets up over 1.5 s, stays up long
            # enough to re-arm, then has a second, distinct fall at 10.5 s.
            lying = fall_then_get_up(t, 2.5) if t < 10.5 else fall_progress(t, 10.5)
            shuffle = 3 * np.sin(4 * t) if 3.1 < t < 6.1 else 0.0
            return [person(t, 20 + shuffle, 60, w=30, h=90, lying=lying)]
        _, incidents, _ = run(scene, 14)
        self.assertEqual(len(incidents), 2)
        self.assertEqual({tid for tid, _ in incidents}, {1})
        self.assertGreater(incidents[1][1], 10.5)

    def test_person_entering_late_and_falling_at_the_very_end_is_caught(self):
        def scene(t):
            people = [person(t, 20, 60, w=30, h=90)]
            if t >= 3.0:
                people.append(person(t, 250, 60, w=30, h=90, lying=fall_progress(t, 6.9, 0.4)))
            return people
        _, incidents, _ = run(scene, 7.5)
        self.assertEqual([tid for tid, _ in incidents], [2])  # caught by the end-of-clip drain

    def test_fall_soon_after_the_clip_starts(self):
        # Two seconds of history are required, so a fall at 2.2 s is the earliest testable.
        _, incidents, _ = run(lambda t: [person(t, 20, 60, w=30, h=90, lying=fall_progress(t, 2.2))], 5)
        self.assertEqual(len(incidents), 1)

    def test_long_video_with_many_falls_by_several_people(self):
        def scene(t):
            people = []
            for i, start in enumerate([4.0, 14.0, 24.0]):
                # person i falls at start, lies 3 s, stands up; falls again 25 s later.
                phase = t - start
                lying = fall_then_get_up(phase % 25, 0.0) if phase >= 0 else 0.0
                people.append(person(t, 20 + 120 * i, 60, w=30, h=90, lying=lying))
            return people
        _, incidents, _ = run(scene, 60)
        per_person = {tid: sum(1 for i, _ in incidents if i == tid) for tid in (1, 2, 3)}
        self.assertEqual(per_person, {1: 3, 2: 2, 3: 2})  # starts at 4, 29, 54 / 14, 39 / 24, 49

    def test_each_window_counts_only_its_own_poses(self):
        def scene(t):
            people = [person(t, 20, 60, w=30, h=90)]
            if t >= 1.0:
                people.append(person(t, 250, 60, w=30, h=90))
            return people
        predictions, _, _ = run(scene, 4)
        first = {tid: next(p for p in predictions if p["track_id"] == tid) for tid in (1, 2)}
        self.assertEqual(first[1]["source_pose_count"], 13)   # 0.0 .. 2.0 s at 6 fps
        self.assertEqual(first[2]["source_pose_count"], 13)   # 1.0 .. 3.0 s, not person 1's
        self.assertAlmostEqual(first[2]["window_start_seconds"], 1.0, places=5)

    def test_live_cap_spreads_work_and_still_classifies_everyone(self):
        scene = lambda t: [person(t, 15 + 75 * i, 60, w=30, h=90) for i in range(5)]
        predictions, _, session = run(scene, 4, max_per_frame=2, drain=False)
        per_frame = {}
        for p in predictions:
            per_frame.setdefault(p["timestamp_seconds"], []).append(p["track_id"])
        self.assertLessEqual(max(len(v) for v in per_frame.values()), 2)
        self.assertEqual({p["track_id"] for p in predictions}, {1, 2, 3, 4, 5})

    def test_people_who_leave_free_their_state(self):
        def scene(t):
            return [person(t, 20, 60, w=30, h=90)] + ([person(t, 250, 60, w=30, h=90)] if t < 2 else [])
        _, _, session = run(scene, 6, track_max_age_seconds=1.0)
        self.assertEqual(sorted(session.people), [1])
        self.assertEqual(session.tracker.ids_issued, 2)

    def test_partially_visible_person_with_low_joint_confidence_is_still_tracked(self):
        scene = lambda t: [person(t, 20, 60, w=30, h=90, confidence=0.35), person(t, 200, 60, w=30, h=90)]
        predictions, _, _ = run(scene, 4)
        self.assertEqual({p["track_id"] for p in predictions}, {1, 2})

    def test_confirmation_setting_delays_but_does_not_drop_a_fall(self):
        scene = lambda t: [person(t, 20, 60, w=30, h=90, lying=fall_progress(t, 3.0))]
        _, once, _ = run(scene, 8)
        _, twice, _ = run(scene, 8, confirmations=2)
        self.assertEqual((len(once), len(twice)), (1, 1))
        self.assertGreater(twice[0][1], once[0][1])


class IncidentRuleTests(unittest.TestCase):
    def test_per_person_rule_equals_the_original_rule_for_one_person(self):
        rng = np.random.default_rng(3)
        for _ in range(200):
            sequence = rng.choice([0.05, 0.2, 0.4, 0.55, 0.9], size=40)
            original, per_person = IncidentTracker(), PersonIncidents()
            self.assertEqual([original.observe(p) for p in sequence],
                             [per_person.observe(1, p) for p in sequence])

    def test_one_persons_low_predictions_never_rearm_another(self):
        book = PersonIncidents()
        self.assertTrue(book.observe(1, 0.9))
        for _ in range(5):
            book.observe(2, 0.05)
        self.assertTrue(book.latched(1))
        self.assertFalse(book.observe(1, 0.9))   # still the same continuing event
        self.assertTrue(book.any_latched())


if __name__ == "__main__":
    unittest.main()
