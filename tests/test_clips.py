"""Fall clips: windows, cutting from uploads, live recording, storage cap and expiry.

The detector here is a scripted test adapter (it emits a fall at a chosen time);
nothing in this file measures detection accuracy. Video is encoded and decoded by
the real OpenCV, and tests that need an encoder skip when this build has none.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from fastapi.testclient import TestClient

from icare.api.clips import ClipEncodeError, ClipManager, ClipWriter, LiveClipRecorder, clip_window
from icare.api.config import Settings
from icare.api.live import LiveManager
from icare.api.main import create_app
from icare.api.schemas import Clip, ClipList, LiveFrame, Result
from icare.api.store import Store

POSE = {"bbox_xyxy": [1, 2, 30, 90], "keypoints": [[10.0, 20.0, 0.9]] * 17}
FPS = 30


def encoder_available() -> bool:
    with tempfile.TemporaryDirectory() as folder:
        try:
            writer = ClipWriter(Path(folder), "probe", 10, (64, 48))
        except ClipEncodeError:
            return False
        writer.abort()
        return True


needs_encoder = unittest.skipUnless(encoder_available(), "this OpenCV build has no H.264 or VP8 encoder")


def write_video(path: Path, seconds: int = 12, size=(320, 240)) -> Path:
    """Frame brightness is 20 + 10 * whole seconds, so a clip's start can be read back."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, size)
    for index in range(seconds * FPS):
        writer.write(np.full((size[1], size[0], 3), 20 + 10 * (index // FPS), np.uint8))
    writer.release()
    return path


def read_clip(path: Path) -> tuple[int, float, float, float]:
    """(frames, fps, first-frame brightness, last-frame brightness) of a saved clip."""
    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(float(frame.mean()))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return len(frames), fps, frames[0], frames[-1]


class ScriptedEngine:
    """TEST ADAPTER: 6 predictions/s for one person who 'falls' at ``fall_at`` seconds."""

    ready = True
    model_version = "test-engine"

    def __init__(self, fall_at=5.0, falls=None, duration=12.0):
        self.falls = falls if falls is not None else ([fall_at] if fall_at is not None else [])
        self.duration = duration
        self.calls = 0

    def analyze_video(self, video_path, *, on_pose, on_prediction, on_progress, cancel_event):
        self.calls += 1
        for step in range(int(self.duration * 6)):
            t = round(step / 6, 6)
            if t < 2.0:
                continue
            high = any(abs(t - fall) < 0.05 for fall in self.falls)
            on_pose({"track_id": 1, "timestamp_seconds": t, **POSE})
            on_prediction({"track_id": 1, "timestamp_seconds": t, "fall_probability": 0.9 if high else 0.05})
        return {"duration_seconds": self.duration, "frame_width": 320, "frame_height": 240, "metrics": {}}

    def close(self):
        pass


class WindowTests(unittest.TestCase):
    def test_four_second_window_around_the_detection(self):
        self.assertEqual(clip_window(10.0, 3.0, 1.0), (7.0, 11.0))

    def test_window_slides_instead_of_shrinking_at_the_edges(self):
        self.assertEqual(clip_window(1.0, 3.0, 1.0), (0.0, 4.0))
        self.assertEqual(clip_window(59.9, 3.0, 1.0, duration=60.0), (56.0, 60.0))

    def test_window_is_clamped_for_sources_shorter_than_the_clip(self):
        self.assertEqual(clip_window(1.0, 3.0, 1.0, duration=2.5), (0.0, 2.5))


@needs_encoder
class ClipManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = Store(self.tmp / "db.sqlite3")
        self.video = write_video(self.tmp / "source.mp4")

    def manager(self, **overrides):
        options = dict(max_bytes=10**9, retention_seconds=86400.0, pre_seconds=3.0, post_seconds=1.0, max_per_job=10)
        options.update(overrides)
        return ClipManager(self.store, self.tmp / "clips", **options)

    def incident(self, name, at):
        return {"incident_id": name, "track_id": 1, "detected_at_seconds": at, "confidence": 0.9}

    def cut(self, manager, job, incidents, cancel=None):
        manager.cut_from_video("owner", job, self.video, incidents, 12.0, cancel or threading.Event())

    def test_clip_covers_the_four_seconds_ending_one_second_after_the_fall(self):
        manager = self.manager()
        incident = self.incident("a", 5.0)
        self.cut(manager, "job", [incident])
        row = self.store.get_clip("a")
        self.assertEqual((incident["clip_id"], row["status"]), ("a", "ready"))
        self.assertAlmostEqual(row["clip_start_seconds"], 2.0, places=2)
        self.assertAlmostEqual(row["duration_seconds"], 4.0, delta=0.05)
        frames, fps, first, last = read_clip(manager.path_of(row))
        self.assertAlmostEqual(frames / fps, 4.0, delta=0.2)
        self.assertAlmostEqual(first, 20 + 10 * 2, delta=8)   # starts in second 2
        self.assertAlmostEqual(last, 20 + 10 * 5, delta=8)    # ends in second 5, just after the fall

    def test_several_incidents_are_cut_in_one_pass(self):
        manager = self.manager()
        incidents = [self.incident("a", 4.0), self.incident("b", 8.0), self.incident("c", 8.5)]
        self.cut(manager, "job", incidents)
        self.assertEqual({r["clip_id"]: r["status"] for r in self.store.clips_for_source("job")},
                         {"a": "ready", "b": "ready", "c": "ready"})

    def test_per_job_limit_leaves_extra_incidents_without_a_clip(self):
        manager = self.manager(max_per_job=2)
        incidents = [self.incident(n, t) for n, t in (("a", 4.0), ("b", 6.0), ("c", 8.0))]
        self.cut(manager, "job", incidents)
        self.assertEqual([i.get("clip_id") for i in incidents], ["a", "b", None])

    def test_storage_cap_evicts_the_oldest_clips_first(self):
        probe = self.manager()
        self.cut(probe, "probe", [self.incident("probe", 5.0)])
        size = self.store.get_clip("probe")["size_bytes"]
        probe.delete("probe")
        manager = self.manager(max_bytes=int(size * 2.5))
        for name, at in (("a", 4.0), ("b", 6.0), ("c", 8.0)):
            self.cut(manager, f"job-{name}", [self.incident(name, at)])
        remaining = [row["clip_id"] for row in self.store.ready_clips_oldest_first()]
        self.assertEqual(remaining, ["b", "c"])
        self.assertLessEqual(self.store.clip_bytes(), manager.max_bytes)
        self.assertEqual(sorted(p.name for p in manager.directory.iterdir()),
                         sorted(self.store.clip_file_names()))  # evicted files are gone from disk

    def test_a_clip_larger_than_the_whole_cap_is_not_kept(self):
        manager = self.manager(max_bytes=100)
        self.cut(manager, "job", [self.incident("a", 5.0)])
        row = self.store.get_clip("a")
        self.assertEqual((row["status"], row["size_bytes"]), ("failed", 0))
        self.assertEqual(list(manager.directory.iterdir()), [])

    def test_clips_expire_after_the_retention_period(self):
        manager = self.manager(retention_seconds=3600.0)
        self.cut(manager, "job", [self.incident("old", 5.0), self.incident("new", 8.0)])
        stale = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        self.store.update_clip("old", created_at_utc=stale)
        manager.remove_expired()
        self.assertIsNone(self.store.get_clip("old"))
        self.assertEqual([row["clip_id"] for row in self.store.list_clips("owner")], ["new"])
        self.assertEqual(sorted(p.name for p in manager.directory.iterdir()), sorted(self.store.clip_file_names()))
        self.assertIsNone(manager.owned("old", "owner"))

    def test_expired_clip_is_refused_even_before_the_sweep_runs(self):
        manager = self.manager(retention_seconds=3600.0)
        self.cut(manager, "job", [self.incident("a", 5.0)])
        self.store.update_clip("a", created_at_utc=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())
        self.assertIsNone(manager.owned("a", "owner"))
        self.assertIsNone(self.store.get_clip("a"))

    def test_cancelled_cut_leaves_no_clips_behind(self):
        manager = self.manager()
        cancel = threading.Event()
        cancel.set()
        self.cut(manager, "job", [self.incident("a", 5.0)], cancel)
        self.assertEqual(self.store.clips_for_source("job"), [])
        self.assertEqual(list(manager.directory.iterdir()), [])

    def test_unreadable_source_marks_the_clip_failed_without_raising(self):
        manager = self.manager()
        incident = self.incident("a", 5.0)
        manager.cut_from_video("owner", "job", self.tmp / "missing.mp4", [incident], 12.0, threading.Event())
        self.assertIsNone(incident.get("clip_id"))  # nothing was promised to the result

    def test_startup_removes_orphan_files_and_fails_interrupted_live_clips(self):
        manager = self.manager()
        (manager.directory / "orphan.mp4").write_bytes(b"x")
        manager.create_pending(clip_id="p", owner="o", source_kind="live", source_id="s", track_id=None,
                               detected_at=3.0, confidence=0.9)
        manager.startup()
        self.assertEqual(list(manager.directory.iterdir()), [])
        self.assertEqual(self.store.get_clip("p")["status"], "failed")


@needs_encoder
class ApiClipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.video = write_video(self.tmp / "source.mp4")
        self.engine = ScriptedEngine(fall_at=5.0)
        settings = Settings(data_dir=self.tmp / "data", job_timeout_seconds=60)
        self.app = create_app(settings, engine=self.engine)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def analyse(self, client=None):
        client = client or self.client
        response = client.post("/api/v1/jobs/upload", files={"file": ("v.mp4", self.video.read_bytes(), "video/mp4")})
        self.assertEqual(response.status_code, 202, response.text)
        job_id = response.json()["job_id"]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            job = client.get(f"/api/v1/jobs/{job_id}").json()
            if job["state"] in ("completed", "failed", "cancelled"):
                return job
            time.sleep(0.05)
        self.fail("job did not finish")

    def test_upload_fall_arrives_as_a_playable_clip_with_its_timestamps(self):
        job = self.analyse()
        self.assertEqual(job["state"], "completed", job)
        result = Result.model_validate(self.client.get(job["result_url"]).json())
        incident = result.incidents[0]
        self.assertIsNotNone(incident.clip_id)

        listing = ClipList.model_validate(self.client.get("/api/v1/clips").json())
        clip = listing.clips[0]
        self.assertEqual((clip.clip_id, clip.status, clip.source_kind, clip.source_id),
                         (incident.clip_id, "ready", "upload", job["job_id"]))
        self.assertAlmostEqual(clip.detected_at_seconds, incident.detected_at_seconds)
        self.assertAlmostEqual(clip.clip_start_seconds, 1.0, places=1)   # the model's 4 s window before the fall
        self.assertAlmostEqual(clip.duration_seconds, 5.0, delta=0.1)
        self.assertGreater(clip.expires_at_utc, clip.created_at_utc)
        self.assertEqual(listing.storage_cap_bytes, 1024 ** 3)
        self.assertEqual(listing.retention_seconds, 86400)
        self.assertEqual(Clip.model_validate(self.client.get(f"/api/v1/clips/{clip.clip_id}").json()), clip)

        video = self.client.get(clip.video_url)
        self.assertEqual((video.status_code, video.headers["content-type"]), (200, clip.media_type))
        picture = self.client.get(clip.snapshot_url)
        self.assertEqual((picture.status_code, picture.headers["content-type"]), (200, "image/jpeg"))
        self.assertEqual(len(video.content) + len(picture.content), clip.size_bytes)  # both count towards the cap
        self.assertEqual(self.client.get(clip.video_url, headers={"Range": "bytes=0-9"}).status_code, 206)
        self.assertEqual(video.headers["cache-control"], "private, no-store")

    def test_a_clip_belongs_to_the_browser_that_uploaded_the_video(self):
        self.analyse()
        clip = self.client.get("/api/v1/clips").json()["clips"][0]
        stranger = TestClient(self.app)
        self.assertEqual(stranger.get("/api/v1/clips").json()["clips"], [])
        self.assertEqual(stranger.get(f"/api/v1/clips/{clip['clip_id']}").status_code, 404)
        self.assertEqual(stranger.get(clip["video_url"]).status_code, 404)
        self.assertEqual(stranger.delete(f"/api/v1/clips/{clip['clip_id']}").status_code, 404)

    def test_deleting_the_job_deletes_its_clips_and_files(self):
        job = self.analyse()
        clips_dir = self.tmp / "data" / "clips"
        self.assertEqual(len(list(clips_dir.iterdir())), 2)   # the video and the picture of the fall
        self.assertEqual(self.client.delete(f"/api/v1/jobs/{job['job_id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/clips").json()["clips"], [])
        self.assertEqual(list(clips_dir.iterdir()), [])

    def test_owner_can_delete_a_clip_without_deleting_the_job(self):
        job = self.analyse()
        clip_id = self.client.get("/api/v1/clips").json()["clips"][0]["clip_id"]
        self.assertEqual(self.client.delete(f"/api/v1/clips/{clip_id}").status_code, 204)
        self.assertEqual(self.client.get(f"/api/v1/clips/{clip_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/jobs/{job['job_id']}").json()["state"], "completed")

    def test_pending_clip_video_is_a_409_not_a_broken_file(self):
        self.analyse()
        first = self.client.get("/api/v1/clips").json()["clips"][0]
        owner = self.app.state.store.get_clip(first["clip_id"])["owner"]
        self.app.state.clips.create_pending(clip_id="pending1", owner=owner, source_kind="live", source_id="s",
                                            track_id=None, detected_at=3.0, confidence=0.9)
        response = self.client.get("/api/v1/clips/pending1/video")
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (409, "clip_pending"))

    def test_video_without_a_fall_makes_no_clip(self):
        self.engine.falls = []
        job = self.analyse()
        self.assertEqual(job["state"], "completed")
        self.assertEqual(self.client.get("/api/v1/clips").json()["clips"], [])

    def test_two_falls_in_one_video_give_two_clips(self):
        self.engine.falls = [4.0, 9.0]
        self.analyse()
        clips = self.client.get("/api/v1/clips").json()["clips"]
        self.assertEqual(sorted(round(c["detected_at_seconds"]) for c in clips), [4, 9])

    def test_settings_expose_the_one_gigabyte_cap_and_one_day_expiry_by_default(self):
        settings = Settings()
        self.assertEqual(settings.max_clip_storage_bytes, 1024 ** 3)
        self.assertEqual(settings.clip_retention_seconds, 24 * 3600)
        self.assertEqual((settings.clip_pre_seconds, settings.clip_post_seconds), (4.0, 1.0))
        with self.assertRaises(ValueError):
            Settings(max_clip_storage_bytes=0)


class LiveEngine:
    """TEST ADAPTER: one person; P(fall) is high on the frames listed in ``falls``."""

    ready = True
    model_version = "test-engine"

    def __init__(self, falls):
        self.falls = set(falls)

    def start_stream(self):
        return {}

    def stop_stream(self):
        pass

    def process_frame(self, data, timestamp, *, cancel_event, timeout_seconds):
        probability = 0.9 if round(timestamp, 3) in self.falls else 0.05
        return {"timestamp_seconds": timestamp, "frame_width": 160, "frame_height": 120,
                "status": "monitoring", "track_resets": 0,
                "poses": [{"track_id": 1, "timestamp_seconds": timestamp, **POSE}],
                "predictions": [{"track_id": 1, "timestamp_seconds": timestamp, "fall_probability": probability}],
                "people": [{"track_id": 1, "status": "monitoring", "coverage_seconds": 2.0, "pose_count": 12}]}

    def close(self):
        pass


def jpeg(brightness: int) -> bytes:
    ok, data = cv2.imencode(".jpg", np.full((120, 160, 3), brightness, np.uint8))
    assert ok
    return data.tobytes()


@needs_encoder
class LiveClipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = Store(self.tmp / "db.sqlite3")
        self.clips = ClipManager(self.store, self.tmp / "clips", max_bytes=10**9, retention_seconds=86400.0,
                                 pre_seconds=3.0, post_seconds=1.0, max_per_job=10)
        self.addCleanup(self.clips.close)
        self.settings = SimpleNamespace(admission_window_seconds=3600, max_jobs_per_visitor_window=10, fall_confirmations=1)

    def session(self, falls):
        manager = LiveManager(self.store, LiveEngine(falls), self.settings, self.clips)
        session_id = manager.start("owner")["session_id"]
        manager.session["started"] -= 1000   # allow capture timestamps beyond the real elapsed time
        return manager, session_id

    def send(self, manager, session_id, timestamp):
        ticket = manager.claim(session_id, "owner", timestamp)
        try:
            return LiveFrame.model_validate(manager.process(ticket, jpeg(int(timestamp * 10) % 250), timestamp))
        finally:
            manager.release(ticket)

    def wait_for(self, clip_id, status="ready"):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            row = self.store.get_clip(clip_id)
            if row["status"] == status:
                return row
            time.sleep(0.05)
        self.fail(f"clip never became {status}: {self.store.get_clip(clip_id)}")

    def test_fall_in_a_live_session_is_saved_after_its_last_second(self):
        manager, sid = self.session(falls=[10.0])
        incidents = []
        for step in range(40, 82):   # 6.7 s .. 13.5 s at 6 frames per second
            incidents += self.send(manager, sid, round(step / 6, 3)).incidents
        # frame 60 is exactly t = 10.0 s
        self.assertEqual([i.detected_at_seconds for i in incidents], [10.0])
        clip_id = incidents[0].clip_id
        self.assertIsNotNone(clip_id)
        row = self.wait_for(clip_id)
        self.assertAlmostEqual(row["clip_start_seconds"], 7.0, delta=0.2)
        self.assertAlmostEqual(row["duration_seconds"], 4.0, delta=0.4)
        self.assertEqual(self.store.live_history("owner")[0]["incidents"][0]["clip_id"], clip_id)
        self.assertTrue(self.clips.path_of(row).is_file())
        manager.stop(sid, "owner")

    def test_clip_is_pending_until_the_second_after_the_fall_has_arrived(self):
        manager, sid = self.session(falls=[10.0])
        for step in range(40, 61):
            frame = self.send(manager, sid, round(step / 6, 3))
        clip_id = frame.incidents[0].clip_id
        self.assertEqual(self.store.get_clip(clip_id)["status"], "pending")
        self.assertEqual(self.clips.document(self.store.get_clip(clip_id))["video_url"], None)
        manager.stop(sid, "owner")

    def test_stopping_the_session_saves_a_clip_that_is_still_waiting(self):
        manager, sid = self.session(falls=[10.0])
        for step in range(40, 63):   # stops 2 frames after the fall
            frame = self.send(manager, sid, round(step / 6, 3))
        self.assertEqual(frame.incidents, [])  # the fall was detected earlier; its clip is still open
        manager.stop(sid, "owner")
        incident_id = self.store.live_history("owner")[0]["incidents"][0]["clip_id"]
        row = self.wait_for(incident_id)
        self.assertGreater(row["duration_seconds"], 3.0)

    def test_session_with_no_fall_writes_no_video_at_all(self):
        manager, sid = self.session(falls=[])
        for step in range(40, 80):
            self.send(manager, sid, round(step / 6, 3))
        manager.stop(sid, "owner")
        self.assertEqual(self.store.list_clips("owner"), [])
        self.assertEqual(list(self.clips.directory.iterdir()), [])

    def test_buffer_keeps_only_a_few_seconds_of_frames(self):
        recorder = LiveClipRecorder(self.clips, "owner", "s")
        for step in range(600):   # 100 s of frames
            recorder.add_frame(step / 6, b"x" * 1000)
        self.assertLess(len(recorder._frames), 6 * 5)   # pre-roll plus a one-second margin
        self.assertLessEqual(recorder._bytes, 30 * 1000)

    def test_manager_without_clip_support_keeps_working(self):
        manager = LiveManager(self.store, LiveEngine([10.0]), self.settings)
        sid = manager.start("owner")["session_id"]
        manager.session["started"] -= 1000
        frame = None
        for step in range(40, 63):
            frame = self.send(manager, sid, round(step / 6, 3))
        self.assertEqual(self.store.live_history("owner")[0]["incidents"][0]["clip_id"], None)
        manager.stop(sid, "owner")


@needs_encoder
class LiveHttpClipTests(unittest.TestCase):
    """Camera frames posted over HTTP: the live fall comes back through /clips."""

    def test_live_fall_clip_is_listed_and_playable_after_its_last_second(self):
        tmp = Path(tempfile.mkdtemp())
        app = create_app(Settings(data_dir=tmp / "data"), engine=LiveEngine([1.1]))
        with TestClient(app) as client:
            session = client.post("/api/v1/live/sessions").json()["session_id"]
            time.sleep(0.4)   # capture timestamps may lead the session clock by at most 2 s
            incident = None
            for step in range(14):
                timestamp = round(0.1 + step / 6, 3)
                response = client.post(f"/api/v1/live/sessions/{session}/frames?timestamp_seconds={timestamp}",
                                       content=jpeg(60 + step * 5), headers={"Content-Type": "image/jpeg"})
                self.assertEqual(response.status_code, 200, response.text)
                frame = LiveFrame.model_validate(response.json())
                incident = incident or (frame.incidents[0] if frame.incidents else None)
            self.assertIsNotNone(incident)
            self.assertEqual(incident.detected_at_seconds, 1.1)

            deadline = time.monotonic() + 20
            clip = None
            while time.monotonic() < deadline:
                clip = Clip.model_validate(client.get(f"/api/v1/clips/{incident.clip_id}").json())
                if clip.status != "pending":
                    break
                time.sleep(0.05)
            self.assertEqual((clip.status, clip.source_kind, clip.source_id), ("ready", "live", session))
            self.assertAlmostEqual(clip.detected_at_seconds, 1.1)
            self.assertAlmostEqual(clip.clip_start_seconds, 0.1, places=2)   # session began less than 3 s earlier
            self.assertGreater(clip.duration_seconds, 1.5)
            video = client.get(clip.video_url)
            self.assertEqual(video.status_code, 200)
            self.assertLessEqual(len(video.content), clip.size_bytes)   # size also counts the picture
            history = client.get("/api/v1/live/history").json()["sessions"][0]["incidents"][0]
            self.assertEqual(history["clip_id"], incident.clip_id)
            client.delete(f"/api/v1/live/sessions/{session}")


class StoreMigrationTests(unittest.TestCase):
    def test_database_from_before_clips_gains_the_clip_columns_and_table(self):
        import sqlite3
        path = Path(tempfile.mkdtemp()) / "old.sqlite3"
        old = sqlite3.connect(path)
        old.executescript("""
            CREATE TABLE incidents (incident_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, track_id INTEGER,
              detected_at_seconds REAL NOT NULL, confidence REAL NOT NULL, status TEXT NOT NULL,
              created_at_utc TEXT NOT NULL);
            CREATE TABLE live_sessions (session_id TEXT PRIMARY KEY, owner TEXT NOT NULL, state TEXT NOT NULL,
              created_at_utc TEXT NOT NULL, ended_at_utc TEXT, model_version TEXT,
              frames_processed INTEGER NOT NULL DEFAULT 0, error_message TEXT);
            CREATE TABLE live_incidents (incident_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, track_id INTEGER,
              detected_at_seconds REAL NOT NULL, confidence REAL NOT NULL, created_at_utc TEXT NOT NULL);
            INSERT INTO live_sessions VALUES ('s1','o','stopped','2026-01-01',NULL,'m',3,NULL);
            INSERT INTO live_incidents VALUES ('old','s1',1,1.5,0.7,'2026-01-01');""")
        old.commit(); old.close()
        store = Store(path)
        store.add_live_incident({"incident_id": "new", "session_id": "s1", "track_id": 2, "clip_id": "new",
                                 "detected_at_seconds": 2.5, "confidence": 0.8, "created_at_utc": "2026-01-01"})
        rows = store.live_history("o")[0]["incidents"]
        self.assertEqual([(r["incident_id"], r["clip_id"]) for r in rows], [("old", None), ("new", "new")])
        self.assertEqual(store.clip_bytes(), 0)


if __name__ == "__main__":
    unittest.main()
