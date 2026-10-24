"""API layer: per-person incidents in jobs and live sessions, schemas, storage migration."""
import csv
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from icare.api.live import LiveManager
from icare.api.schemas import LiveFrame, Result
from icare.api.store import Store, utc_now
from icare.api.worker import JobRunner

POSE = {"bbox_xyxy": [1, 2, 30, 90], "keypoints": [[10.0, 20.0, 0.9]] * 17}


class ScriptedEngine:
    """Replays engine records: (track_id, timestamp, P(fall)) predictions."""

    ready = True
    model_version = "test-engine"

    def __init__(self, predictions):
        self.predictions = predictions

    def analyze_video(self, video_path, *, on_pose, on_prediction, on_progress, cancel_event):
        for track_id, t, p in self.predictions:
            on_pose({"track_id": track_id, "timestamp_seconds": t, **POSE})
            on_prediction({"track_id": track_id, "timestamp_seconds": t, "fall_probability": p})
        return {"duration_seconds": 20.0, "frame_width": 640, "frame_height": 360, "metrics": {}}

    def close(self):
        pass


def run_job(engine):
    folder = Path(tempfile.mkdtemp())
    store = Store(folder / "db.sqlite3")
    job_id = "job1"
    store.create_job({"job_id": job_id, "owner": "o", "state": "queued", "progress": None,
                      "source_kind": "upload", "media_path": str(folder / "v.mp4"),
                      "created_at_utc": utc_now(), "model_version": None,
                      "error_code": None, "error_message": None})
    (folder / "jobs" / job_id).mkdir(parents=True)
    runner = JobRunner(store, engine, folder / "jobs", timeout_seconds=30)
    runner._run(job_id, threading.Event())
    return store, folder / "jobs" / job_id, store.get_job(job_id)


class JobIncidentTests(unittest.TestCase):
    def test_overlapping_falls_by_two_people_give_two_incidents(self):
        # Person 1 falls at 3.0 and stays high; person 2 falls at 4.5 while 1 is still latched.
        predictions = [(1, 2.0, 0.05), (2, 2.0, 0.05), (1, 3.0, 0.9), (2, 3.0, 0.04),
                       (1, 3.8, 0.95), (2, 3.8, 0.06), (1, 4.5, 0.9), (2, 4.5, 0.8), (1, 5.3, 0.9), (2, 5.3, 0.9)]
        store, folder, job = run_job(ScriptedEngine(predictions))
        self.assertEqual(job["state"], "completed")
        result = Result.model_validate(json.loads((folder / "result.json").read_text()))
        self.assertEqual([(i.track_id, i.detected_at_seconds) for i in result.incidents], [(1, 3.0), (2, 4.5)])
        stored = store.get_incident("job1", result.incidents[1].incident_id)
        self.assertEqual(stored["track_id"], 2)
        with (folder / "report.csv").open(newline="") as file:
            rows = list(csv.DictReader(file))
        marked = [(row["track_id"], row["timestamp_seconds"]) for row in rows if row["incident_id"]]
        self.assertEqual(marked, [("1", "3.0"), ("2", "4.5")])   # same timestamps, right person

    def test_engine_without_track_ids_keeps_the_original_single_rule(self):
        predictions = [(None, 3.0, 0.9), (None, 3.8, 0.9), (None, 4.5, 0.9)]
        _, folder, job = run_job(ScriptedEngine(predictions))
        result = json.loads((folder / "result.json").read_text())
        self.assertEqual(len(result["incidents"]), 1)
        self.assertIsNone(result["incidents"][0]["track_id"])


class StorageMigrationTests(unittest.TestCase):
    def test_database_from_before_tracking_gains_the_person_column(self):
        path = Path(tempfile.mkdtemp()) / "old.sqlite3"
        old = sqlite3.connect(path)
        old.executescript("""
            CREATE TABLE incidents (incident_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
              detected_at_seconds REAL NOT NULL, confidence REAL NOT NULL, status TEXT NOT NULL,
              created_at_utc TEXT NOT NULL);
            CREATE TABLE live_sessions (session_id TEXT PRIMARY KEY, owner TEXT NOT NULL, state TEXT NOT NULL,
              created_at_utc TEXT NOT NULL, ended_at_utc TEXT, model_version TEXT,
              frames_processed INTEGER NOT NULL DEFAULT 0, error_message TEXT);
            CREATE TABLE live_incidents (incident_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
              detected_at_seconds REAL NOT NULL, confidence REAL NOT NULL, created_at_utc TEXT NOT NULL);
            INSERT INTO live_sessions VALUES ('s1','o','stopped','2026-01-01',NULL,'m',3,NULL);
            INSERT INTO live_incidents VALUES ('old','s1',1.5,0.7,'2026-01-01');""")
        old.commit(); old.close()
        store = Store(path)
        store.add_live_incident({"incident_id": "new", "session_id": "s1", "track_id": 3,
                                 "detected_at_seconds": 2.5, "confidence": 0.8, "created_at_utc": "2026-01-01"})
        incidents = store.live_history("o")[0]["incidents"]
        self.assertEqual([(i["incident_id"], i["track_id"]) for i in incidents], [("old", None), ("new", 3)])


class LiveEngine:
    ready = True
    model_version = "test-engine"

    def __init__(self, frames):
        self.frames = iter(frames)

    def start_stream(self):
        return {}

    def stop_stream(self):
        pass

    def process_frame(self, data, timestamp, *, cancel_event, timeout_seconds):
        people = next(self.frames)
        return {"timestamp_seconds": timestamp, "frame_width": 640, "frame_height": 360,
                "status": "monitoring" if people else "no_person", "track_resets": 0,
                "poses": [{"track_id": tid, "timestamp_seconds": timestamp, **POSE} for tid, _ in people],
                "predictions": [{"track_id": tid, "timestamp_seconds": timestamp, "fall_probability": p}
                                for tid, p in people if p is not None],
                "people": [{"track_id": tid, "status": "monitoring", "coverage_seconds": 2.0, "pose_count": 12}
                           for tid, _ in people]}


class LiveIncidentTests(unittest.TestCase):
    def test_each_person_alerts_once_and_latch_survives_brief_absence(self):
        frames = [[(1, 0.1), (2, 0.1)], [(1, 0.9), (2, 0.1)], [(1, 0.9), (2, 0.8)], [(2, 0.9)], [(1, None), (2, 0.9)]]
        settings = SimpleNamespace(admission_window_seconds=3600, max_jobs_per_visitor_window=10, fall_confirmations=1)
        store = Store(Path(tempfile.mkdtemp()) / "db.sqlite3")
        manager = LiveManager(store, LiveEngine(frames), settings)
        session_id = manager.start("owner")["session_id"]
        responses = []
        for index in range(len(frames)):
            ticket = manager.claim(session_id, "owner", 0.2 * (index + 1))
            try:
                responses.append(LiveFrame.model_validate(manager.process(ticket, b"", 0.2 * (index + 1))))
            finally:
                manager.release(ticket)
            time.sleep(0.001)
        self.assertEqual([[i.track_id for i in r.incidents] for r in responses], [[], [1], [2], [], []])
        self.assertEqual([[p.incident_latched for p in r.people] for r in responses][2], [True, True])
        self.assertTrue(responses[3].incident_latched)  # person 1 hidden, their event still open
        manager.stop(session_id, "owner")
        stored = store.live_history("owner")[0]["incidents"]
        self.assertEqual([i["track_id"] for i in stored], [1, 2])


if __name__ == "__main__":
    unittest.main()
