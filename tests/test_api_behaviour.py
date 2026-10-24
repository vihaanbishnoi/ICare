"""Behaviour events through the API: video jobs, live sessions, storage and the listing route.

Synthetic poses exercise plumbing and the event rules, not real-world accuracy.
"""
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from icare.api.config import Settings
from icare.api.live import LiveManager
from icare.api.main import create_app
from icare.api.schemas import BehaviourEventList, LiveFrame, LiveHistoryResponse, Result
from icare.api.store import Store, utc_now
from icare.api.worker import JobRunner
from tests.helpers import person, times
from tests.test_behaviour import pace, record

FAST = dict(inactivity_seconds=20, long_lie_seconds=10)


class PoseEngine:
    """Replays synthetic pose records; ``falls`` are (track_id, t) high P(fall) predictions."""

    ready = True
    model_version = "test-engine"

    def __init__(self, records, falls=()):
        self.records, self.falls = records, set(falls)

    def analyze_video(self, video_path, *, on_pose, on_prediction, on_progress, cancel_event):
        for item in self.records:
            on_pose(item)
            key = (item["track_id"], item["timestamp_seconds"])
            if key in self.falls:
                on_prediction({"track_id": key[0], "timestamp_seconds": key[1], "fall_probability": 0.95})
        return {"duration_seconds": self.records[-1]["timestamp_seconds"], "frame_width": 1280,
                "frame_height": 720, "metrics": {}}

    def close(self):
        pass


def run_job(engine, **settings):
    folder = Path(tempfile.mkdtemp())
    store = Store(folder / "db.sqlite3")
    store.create_job({"job_id": "job1", "owner": "o", "state": "queued", "progress": None,
                      "source_kind": "upload", "media_path": str(folder / "v.mp4"),
                      "created_at_utc": utc_now(), "model_version": None,
                      "error_code": None, "error_message": None})
    (folder / "jobs" / "job1").mkdir(parents=True)
    runner = JobRunner(store, engine, folder / "jobs", timeout_seconds=30,
                       behaviour=Settings(data_dir=folder, **settings).behaviour_monitor)
    runner._run("job1", threading.Event())
    result = Result.model_validate(json.loads((folder / "jobs" / "job1" / "result.json").read_text()))
    return store, result


class JobBehaviourTests(unittest.TestCase):
    def test_pacing_in_a_video_is_reported_stored_and_deleted_with_the_job(self):
        records = [record(person(t, pace(t), 300)) for t in times(40)]
        store, result = run_job(PoseEngine(records), **FAST)
        self.assertEqual([(e.event_type, e.source_kind, e.source_id, e.track_id) for e in result.behaviour_events],
                         [("pacing", "upload", "job1", 1)])
        self.assertEqual(result.behaviour_events[0].end_reason, "source_ended")
        stored = store.list_behaviour_events("o")
        self.assertEqual([e["event_id"] for e in stored], [result.behaviour_events[0].event_id])
        self.assertEqual(store.list_behaviour_events("someone else"), [])
        store.delete_job("job1")
        self.assertEqual(store.list_behaviour_events("o"), [])

    def test_fall_followed_by_staying_down_is_a_long_lie(self):
        records = [record(person(t, 300, 300, lying=0.0 if t < 3 else 1.0)) for t in times(20)]
        _, result = run_job(PoseEngine(records, falls=[(1, 4.0)]), **FAST)
        self.assertEqual(len(result.incidents), 1)
        self.assertEqual([(e.event_type, e.severity, e.start_seconds) for e in result.behaviour_events],
                         [("long_lie", "urgent", 4.0)])

    def test_ordinary_walk_through_gives_no_events(self):
        records = [record(person(t, 50 + 25 * t, 300)) for t in times(30)]
        _, result = run_job(PoseEngine(records), **FAST)
        self.assertEqual(result.behaviour_events, [])

    def test_events_can_be_disabled(self):
        records = [record(person(t, pace(t), 300)) for t in times(40)]
        _, result = run_job(PoseEngine(records), behaviour_enabled=False, **FAST)
        self.assertEqual(result.behaviour_events, [])


class LiveEngine:
    ready = True
    model_version = "test-engine"

    def __init__(self, x_at):
        self.x_at = x_at

    def start_stream(self):
        return {}

    def stop_stream(self):
        pass

    def process_frame(self, data, timestamp, *, cancel_event, timeout_seconds):
        pose = record(person(timestamp, self.x_at(timestamp), 300))
        return {"timestamp_seconds": timestamp, "frame_width": 1280, "frame_height": 720,
                "status": "monitoring", "track_resets": 0, "poses": [pose], "predictions": [],
                "people": [{"track_id": 1, "status": "monitoring", "coverage_seconds": 2.0, "pose_count": 12}]}


class LiveBehaviourTests(unittest.TestCase):
    def test_stillness_opens_one_event_shows_progress_and_is_closed_on_stop(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()), admission_window_seconds=3600, **FAST)
        store = Store(settings.data_dir / "db.sqlite3")
        manager = LiveManager(store, LiveEngine(lambda t: 300.0), settings)
        session_id = manager.start("owner")["session_id"]
        session = manager.session
        frames = []
        for t in times(25)[1:]:
            # Bypasses claim(): its wall-clock check would make this test take 25 s.
            frames.append(LiveFrame.model_validate(manager.process(session, b"", t)))
        opened = [(f.timestamp_seconds, e.event_type) for f in frames for e in f.behaviour_events]
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0][1], "prolonged_inactivity")
        self.assertGreaterEqual(opened[0][0], 20)
        last = frames[-1].people[0].behaviour
        self.assertEqual(last.evidence, "good")
        self.assertGreater(last.still_seconds, 20)
        self.assertEqual(last.active_events, ["prolonged_inactivity"])
        manager.stop(session_id, "owner")
        history = LiveHistoryResponse.model_validate({"sessions": store.live_history("owner")})
        events = history.sessions[0].behaviour_events
        self.assertEqual([(e.event_type, e.end_reason) for e in events], [("prolonged_inactivity", "source_ended")])


class RouteTests(unittest.TestCase):
    def test_listing_returns_this_browsers_events_only(self):
        tmp = Path(tempfile.mkdtemp())
        app = create_app(Settings(data_dir=tmp / "data"), engine=None)
        event = {"event_id": "e1", "source_kind": "live", "source_id": "s", "track_id": 1, "event_type": "pacing",
                 "severity": "attention", "start_seconds": 1.0, "detected_at_seconds": 20.0, "end_seconds": None,
                 "end_reason": None, "evidence": {"turns": 4.0}, "created_at_utc": utc_now()}
        with TestClient(app) as client, TestClient(app) as stranger:
            self.assertEqual(client.get("/api/v1/behaviour/events").json(), {"events": []})  # sets the cookie
            owner = hashlib.sha256(client.cookies.get("icare_session").encode()).hexdigest()
            app.state.store.save_behaviour_event(owner, event)
            listed = BehaviourEventList.model_validate(client.get("/api/v1/behaviour/events").json()).events
            self.assertEqual([(e.event_id, e.evidence) for e in listed], [("e1", {"turns": 4.0})])
            self.assertEqual(stranger.get("/api/v1/behaviour/events").json(), {"events": []})

if __name__ == "__main__":
    unittest.main()
