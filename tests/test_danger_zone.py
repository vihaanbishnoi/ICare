"""Rooms and danger zones: fall location, per-fall picture, room photo, shared zone data.

Detectors here are scripted test adapters whose people fall on a script; nothing in
this file measures how well real falls are located. Video is real OpenCV.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from fastapi.testclient import TestClient

from icare.api.clips import ClipManager, LiveClipRecorder
from icare.api.config import Settings
from icare.api.danger import ZoneManager, estimate_fall_location, render_snapshot, valid_room
from icare.api.live import LiveManager
from icare.api.main import create_app
from icare.api.schemas import Clip, DangerZone, LiveFrame, RoomList
from icare.api.store import Store
from tests.test_clips import jpeg, needs_encoder, write_video

W, H = 320, 240


def standing(x=160.0):
    """A person standing with their feet at (x, 215): hips at y=130, shoulders at y=90."""
    keypoints = [[x, 100.0, 0.9] for _ in range(17)]
    for joint in (5, 6):
        keypoints[joint] = [x, 90.0, 0.9]
    for joint in (11, 12):
        keypoints[joint] = [x, 130.0, 0.9]
    for joint in (15, 16):
        keypoints[joint] = [x, 215.0, 0.9]
    return {"bbox_xyxy": [x - 20, 60.0, x + 20, 220.0], "keypoints": keypoints}


def lying(x=240.0):
    keypoints = [[x, 200.0, 0.9] for _ in range(17)]
    return {"bbox_xyxy": [x - 60, 170.0, x + 60, 225.0], "keypoints": keypoints}


def fall_track(start=4.0, end=5.0, until=5.0, step=1 / 6, begin=2.0, track_id=1, stand_x=160.0, land_x=240.0):
    """Person stands at stand_x, loses balance from ``start``, is on the floor at land_x by ``end``."""
    poses, t = [], begin
    while t <= until + 1e-9:
        if t < start:
            pose = standing(stand_x)
        elif t >= end:
            pose = lying(land_x)
        else:
            mix = (t - start) / (end - start)
            a, b = standing(stand_x), lying(land_x)
            pose = {"bbox_xyxy": [x + (y - x) * mix for x, y in zip(a["bbox_xyxy"], b["bbox_xyxy"])],
                    "keypoints": [[ax + (bx - ax) * mix, ay + (by - ay) * mix, 0.9]
                                  for (ax, ay, _), (bx, by, _) in zip(a["keypoints"], b["keypoints"])]}
        poses.append({"track_id": track_id, "timestamp_seconds": round(t, 6), **pose})
        t += step
    return poses


class RoomNameTests(unittest.TestCase):
    def test_accepts_room_names_and_rejects_the_rest(self):
        self.assertIsNone(valid_room(None))
        self.assertIsNone(valid_room(""))
        self.assertEqual(valid_room("101"), "101")
        self.assertEqual(valid_room("East lounge-2"), "East lounge-2")
        for bad in ("../etc", "a" * 40, " 101", "room/1", "<b>"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                valid_room(bad)


class LocationTests(unittest.TestCase):
    def test_onset_is_where_they_stood_when_the_descent_began(self):
        location = estimate_fall_location(fall_track(), 5.0, W, H)
        self.assertTrue(location["onset_estimated"])
        self.assertGreaterEqual(location["onset_seconds"], 4.0)
        self.assertLess(location["onset_seconds"], 4.5)
        self.assertAlmostEqual(location["onset_x"], 160 / W, delta=0.08)    # where they stood
        self.assertAlmostEqual(location["onset_y"], 215 / H, delta=0.08)    # their feet
        self.assertAlmostEqual(location["landing_x"], 240 / W, delta=0.01)  # where they ended up
        self.assertAlmostEqual(location["landing_y"], 197.5 / H, delta=0.01)
        self.assertGreater(abs(location["landing_x"] - location["onset_x"]), 0.2)
        self.assertEqual(location["snapshot_seconds"], location["onset_seconds"])
        self.assertEqual((location["frame_width"], location["frame_height"]), (W, H))

    def test_without_a_clear_descent_onset_repeats_landing_and_says_so(self):
        track = [{"track_id": 1, "timestamp_seconds": 2 + i / 6, **standing()} for i in range(12)]
        location = estimate_fall_location(track, track[-1]["timestamp_seconds"], W, H)
        self.assertFalse(location["onset_estimated"])
        self.assertIsNone(location["onset_seconds"])
        self.assertEqual((location["onset_x"], location["onset_y"]), (location["landing_x"], location["landing_y"]))
        self.assertEqual(location["snapshot_seconds"], track[-1]["timestamp_seconds"])

    def test_poses_after_the_detection_are_ignored(self):
        track = fall_track(until=9.0)
        early = estimate_fall_location(track, 5.0, W, H)
        late = estimate_fall_location([p for p in track if p["timestamp_seconds"] <= 5.0], 5.0, W, H)
        self.assertEqual(early, late)

    def test_ankles_that_are_not_visible_fall_back_to_the_bottom_of_the_box(self):
        track = fall_track()
        for pose in track:
            for joint in (15, 16):
                pose["keypoints"][joint][2] = 0.0
        location = estimate_fall_location(track, 5.0, W, H)
        self.assertTrue(location["onset_estimated"])
        self.assertAlmostEqual(location["onset_y"], 220 / H, delta=0.1)   # bottom edge of the standing box

    def test_nothing_to_go_on_gives_no_location(self):
        self.assertIsNone(estimate_fall_location([], 5.0, W, H))
        self.assertIsNone(estimate_fall_location(fall_track(), 5.0, 0, H))

    def test_positions_are_normalised_and_kept_inside_the_frame(self):
        track = [{"track_id": 1, "timestamp_seconds": 2 + i / 6, **standing(-500.0)} for i in range(6)]
        location = estimate_fall_location(track, 3.0, W, H)
        for key in ("onset_x", "onset_y", "landing_x", "landing_y", "body_width"):
            self.assertTrue(0.0 <= location[key] <= 1.0, key)


class SnapshotTests(unittest.TestCase):
    def test_picture_highlights_a_red_area_where_the_fall_began(self):
        location = estimate_fall_location(fall_track(), 5.0, W, H)
        data = render_snapshot(np.full((H, W, 3), 90, np.uint8), location)
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(image.shape[:2], (H, W))
        x, y = round(location["onset_x"] * (W - 1)), round(location["onset_y"] * (H - 1))

        def redness(px, py):
            b, g, r = (int(v) for v in image[py, px])
            return r - (b + g) / 2

        area = [redness(min(W - 1, x + dx), y - 16) for dx in (-20, 0, 20)]   # inside the glow, off the white ring
        far = redness(min(W - 1, x + 150), 20)                                # well away from it
        self.assertTrue(all(value > 40 for value in area), area)   # a clearly red area, not a thin line
        self.assertLess(abs(far), 15)                              # the rest of the picture is untouched

    def test_landing_is_an_orange_area_when_the_start_was_found(self):
        location = estimate_fall_location(fall_track(), 5.0, W, H)
        image = cv2.imdecode(np.frombuffer(render_snapshot(np.full((H, W, 3), 90, np.uint8), location), np.uint8), cv2.IMREAD_COLOR)
        x, y = round(location["landing_x"] * (W - 1)), round(location["landing_y"] * (H - 1))
        b, g, r = (int(v) for v in image[y, x])
        self.assertGreater(r - b, 60)    # orange: strong red, some green, little blue
        self.assertGreater(g, b + 20)

    def test_without_a_found_start_only_the_red_area_is_drawn(self):
        track = [{"track_id": 1, "timestamp_seconds": 2 + i / 6, **standing()} for i in range(12)]
        location = estimate_fall_location(track, track[-1]["timestamp_seconds"], W, H)
        self.assertFalse(location["onset_estimated"])
        image = cv2.imdecode(np.frombuffer(render_snapshot(np.full((H, W, 3), 90, np.uint8), location), np.uint8), cv2.IMREAD_COLOR)
        self.assertGreater(len(image), 0)

    def test_wide_frames_are_scaled_down(self):
        location = estimate_fall_location(fall_track(), 5.0, 1920, 1080)
        data = render_snapshot(np.zeros((1080, 1920, 3), np.uint8), location)
        self.assertEqual(cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR).shape[1], 960)


class ZoneManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = Store(self.tmp / "db.sqlite3")
        self.zones = ZoneManager(self.store, self.tmp / "rooms")
        self.location = estimate_fall_location(fall_track(), 5.0, W, H)

    def png(self, width=200, height=120):
        ok, data = cv2.imencode(".png", np.full((height, width, 3), 120, np.uint8))
        return data.tobytes()

    def add(self, fall_id, room="101"):
        self.zones.record(fall_id=fall_id, room=room, source_kind="live", source_id="s", track_id=1,
                          detected_at_seconds=5.0, confidence=0.9, location=self.location)

    def test_photo_is_validated_resized_and_replaceable(self):
        for bad in (b"not an image", b"", self.png(20, 20)):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                self.zones.set_photo("101", bad, "upload")
        with self.assertRaises(ValueError):
            self.zones.set_photo("101", b"x" * (5 * 1024 * 1024), "upload")
        first = self.zones.set_photo("101", self.png(2000, 1000), "upload")
        self.assertEqual((first["width"], first["height"]), (1280, 640))
        second = self.zones.set_photo("101", self.png(300, 200), "upload")
        self.assertEqual((second["width"], second["height"]), (300, 200))
        self.assertEqual(len(list(self.zones.directory.iterdir())), 1)   # replaced, not accumulated

    def test_auto_photo_never_overwrites_a_chosen_one(self):
        self.assertTrue(self.zones.ensure_photo("101", np.full((100, 100, 3), 50, np.uint8)))
        self.assertFalse(self.zones.ensure_photo("101", np.full((100, 100, 3), 200, np.uint8)))
        self.assertEqual(self.zones.store.get_room_photo("101")["source"], "auto")

    def test_zone_lists_a_rooms_falls_newest_first_and_only_that_room(self):
        self.add("a"); time.sleep(0.01); self.add("b"); self.add("other", room="102")
        zone = DangerZone.model_validate(self.zones.zone("101"))
        self.assertEqual([f.fall_id for f in zone.falls], ["b", "a"])
        self.assertEqual((zone.total_falls, zone.frame_width, zone.frame_height), (2, W, H))
        self.assertEqual([r["room"] for r in self.zones.rooms()], ["101", "102"])

    def test_a_fall_can_be_removed_and_removal_is_exact(self):
        self.add("a"); self.add("b")
        self.assertFalse(self.zones.remove_fall("102", "a"))
        self.assertTrue(self.zones.remove_fall("101", "a"))
        self.assertEqual([f["fall_id"] for f in self.zones.zone("101")["falls"]], ["b"])

    def test_startup_removes_photo_files_nothing_refers_to(self):
        self.zones.set_photo("101", self.png(), "upload")
        (self.zones.directory / "stray.jpg").write_bytes(b"x")
        self.zones.startup()
        self.assertEqual(len(list(self.zones.directory.iterdir())), 1)


class FallingEngine:
    """TEST ADAPTER: one person who falls at 4.0 s and is detected at 5.0 s."""

    ready = True
    model_version = "test-engine"

    def analyze_video(self, video_path, *, on_pose, on_prediction, on_progress, cancel_event):
        for pose in fall_track(until=11.0):
            on_pose(pose)
            t = pose["timestamp_seconds"]
            on_prediction({"track_id": 1, "timestamp_seconds": t, "fall_probability": 0.9 if abs(t - 5.0) < 0.05 else 0.05})
        return {"duration_seconds": 12.0, "frame_width": W, "frame_height": H, "metrics": {}}

    def close(self):
        pass


@needs_encoder
class RoomApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.video = write_video(self.tmp / "source.mp4")
        self.app = create_app(Settings(data_dir=self.tmp / "data", job_timeout_seconds=60), engine=FallingEngine())
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def analyse(self, room=None, client=None):
        client = client or self.client
        query = f"?room={room}" if room is not None else ""
        response = client.post(f"/api/v1/jobs/upload{query}", files={"file": ("v.mp4", self.video.read_bytes(), "video/mp4")})
        self.assertEqual(response.status_code, 202, response.text)
        job_id = response.json()["job_id"]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            job = client.get(f"/api/v1/jobs/{job_id}").json()
            if job["state"] in ("completed", "failed", "cancelled"):
                return job
            time.sleep(0.05)
        self.fail("job did not finish")

    def test_a_fall_in_a_room_shows_up_in_that_rooms_danger_zone_for_everyone(self):
        job = self.analyse(room="101")
        self.assertEqual(job["state"], "completed", job)
        stranger = TestClient(self.app)   # another browser, another caretaker
        zone = DangerZone.model_validate(stranger.get("/api/v1/rooms/101/danger-zone").json())
        self.assertEqual(zone.total_falls, 1)
        fall = zone.falls[0]
        self.assertEqual(fall.source_kind, "upload")
        self.assertTrue(fall.onset_estimated)
        self.assertAlmostEqual(fall.onset_x, 160 / W, delta=0.08)
        self.assertAlmostEqual(fall.landing_x, 240 / W, delta=0.01)
        self.assertEqual([r["room"] for r in stranger.get("/api/v1/rooms").json()["rooms"]], ["101"])
        self.assertEqual(RoomList.model_validate(stranger.get("/api/v1/rooms").json()).rooms[0].fall_count, 1)
        self.assertEqual(stranger.get("/api/v1/rooms/102/danger-zone").json()["falls"], [])

    def test_clip_carries_its_room_and_a_picture_only_its_owner_can_open(self):
        self.analyse(room="101")
        clip = Clip.model_validate(self.client.get("/api/v1/clips").json()["clips"][0])
        self.assertEqual(clip.room, "101")
        picture = self.client.get(clip.snapshot_url)
        self.assertEqual((picture.status_code, picture.headers["content-type"]), (200, "image/jpeg"))
        stranger = TestClient(self.app)
        self.assertEqual(stranger.get(clip.snapshot_url).status_code, 404)

    def test_picture_is_kept_even_when_no_room_was_chosen_but_no_zone_data_is_stored(self):
        self.analyse()
        clip = self.client.get("/api/v1/clips").json()["clips"][0]
        self.assertIsNone(clip["room"])
        self.assertEqual(self.client.get(clip["snapshot_url"]).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/rooms").json()["rooms"], [])

    def test_room_photo_is_taken_from_a_frame_with_nobody_in_it(self):
        self.analyse(room="101")
        photo = self.client.get("/api/v1/rooms/101/photo")
        self.assertEqual((photo.status_code, photo.headers["content-type"]), (200, "image/jpeg"))
        zone = self.client.get("/api/v1/rooms/101/danger-zone").json()
        self.assertTrue(zone["photo_url"].startswith("/api/v1/rooms/101/photo?v="))
        self.assertEqual((zone["frame_width"], zone["frame_height"]), (W, H))

    def test_photo_can_be_replaced_and_bad_uploads_are_refused(self):
        self.analyse(room="101")
        ok, png = cv2.imencode(".png", np.full((90, 160, 3), 60, np.uint8))
        put = self.client.put("/api/v1/rooms/101/photo", content=png.tobytes(), headers={"Content-Type": "image/png"})
        self.assertEqual(put.status_code, 204)
        self.assertEqual(self.client.get("/api/v1/rooms/101/danger-zone").json()["frame_width"], 160)
        for body, kind, status, code in ((b"junk", "image/png", 400, "invalid_photo"),
                                         (png.tobytes(), "text/plain", 400, "invalid_photo"),
                                         (b"x" * (5 * 1024 * 1024), "image/jpeg", 413, "photo_too_large")):
            response = self.client.put("/api/v1/rooms/101/photo", content=body, headers={"Content-Type": kind})
            self.assertEqual((response.status_code, response.json()["error"]["code"]), (status, code))

    def test_zone_data_outlives_the_job_and_the_clip(self):
        job = self.analyse(room="101")
        self.assertEqual(self.client.delete(f"/api/v1/jobs/{job['job_id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/clips").json()["clips"], [])
        zone = self.client.get("/api/v1/rooms/101/danger-zone").json()
        self.assertEqual(zone["total_falls"], 1)
        self.assertIsNotNone(zone["photo_url"])

    def test_zone_data_survives_clip_expiry(self):
        self.analyse(room="101")
        manager = self.app.state.clips
        stale = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        for row in manager.store._read("select clip_id from clips"):
            manager.store.update_clip(row["clip_id"], created_at_utc=stale)
        manager.remove_expired()
        self.assertEqual(manager.store._read("select * from clips"), [])
        self.assertEqual(list(manager.directory.iterdir()), [])
        self.assertEqual(self.client.get("/api/v1/rooms/101/danger-zone").json()["total_falls"], 1)

    def test_a_false_alarm_can_be_removed_from_the_zone(self):
        self.analyse(room="101")
        fall_id = self.client.get("/api/v1/rooms/101/danger-zone").json()["falls"][0]["fall_id"]
        self.assertEqual(self.client.delete(f"/api/v1/rooms/101/falls/{fall_id}").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/rooms/101/danger-zone").json()["total_falls"], 0)
        self.assertEqual(self.client.delete(f"/api/v1/rooms/101/falls/{fall_id}").status_code, 404)

    def test_each_room_keeps_its_own_zone(self):
        self.analyse(room="101"); self.analyse(room="102"); self.analyse(room="102")
        counts = {r["room"]: r["fall_count"] for r in self.client.get("/api/v1/rooms").json()["rooms"]}
        self.assertEqual(counts, {"101": 1, "102": 2})

    def test_invalid_room_names_are_refused_before_any_work(self):
        response = self.client.post("/api/v1/jobs/upload?room=../x", files={"file": ("v.mp4", b"x", "video/mp4")})
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (400, "invalid_room"))
        self.assertEqual(self.client.get("/api/v1/rooms/..%2Fx/danger-zone").status_code in (400, 404), True)
        self.assertEqual(self.client.get("/api/v1/rooms/bad%3Cname/danger-zone").status_code, 400)


class StallingLiveEngine:
    """TEST ADAPTER: nobody in view until 0.8 s, then one person who falls and is detected at 2.0 s."""

    ready = True
    model_version = "test-engine"

    def start_stream(self):
        return {}

    def stop_stream(self):
        pass

    def process_frame(self, data, timestamp, *, cancel_event, timeout_seconds):
        track = fall_track(start=1.4, end=2.0, until=timestamp, begin=0.8, step=1 / 6)
        pose = next((p for p in track if abs(p["timestamp_seconds"] - timestamp) < 0.09), None)
        people = [] if timestamp < 0.8 or pose is None else [pose]
        high = abs(timestamp - 2.0) < 0.09
        return {"timestamp_seconds": timestamp, "frame_width": W, "frame_height": H,
                "status": "monitoring" if people else "no_person", "track_resets": 0,
                "poses": [{"track_id": 1, **{k: v for k, v in p.items() if k != "track_id"}} for p in people],
                "predictions": [{"track_id": 1, "timestamp_seconds": timestamp, "fall_probability": 0.9 if high else 0.05}
                                for _ in people],
                "people": [{"track_id": 1, "status": "monitoring", "coverage_seconds": 2.0, "pose_count": 12} for _ in people]}

    def close(self):
        pass


@needs_encoder
class LiveRoomTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = Store(self.tmp / "db.sqlite3")
        self.clips = ClipManager(self.store, self.tmp / "clips", max_bytes=10**9, retention_seconds=86400.0,
                                 pre_seconds=4.0, post_seconds=1.0, max_per_job=10,
                                 zones=ZoneManager(self.store, self.tmp / "rooms"))
        self.addCleanup(self.clips.close)
        self.settings = SimpleNamespace(admission_window_seconds=3600, max_jobs_per_visitor_window=10, fall_confirmations=1)

    def start(self, room="101"):
        manager = LiveManager(self.store, StallingLiveEngine(), self.settings, self.clips)
        session_id = manager.start("owner", room)["session_id"]
        manager.session["started"] -= 1000
        return manager, session_id

    def send(self, manager, session_id, timestamp):
        ticket = manager.claim(session_id, "owner", timestamp)
        try:
            return LiveFrame.model_validate(manager.process(ticket, jpeg(int(timestamp * 20) % 250), timestamp))
        finally:
            manager.release(ticket)

    def wait_for(self, clip_id):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            row = self.store.get_clip(clip_id)
            if row["status"] != "pending":
                return row
            time.sleep(0.05)
        self.fail("clip stayed pending")

    def run_session(self, last_step=24, room="101"):
        manager, session_id = self.start(room)
        incident = None
        for step in range(1, last_step + 1):
            frame = self.send(manager, session_id, round(step / 6, 3))
            incident = incident or (frame.incidents[0] if frame.incidents else None)
        return manager, session_id, incident

    def test_live_fall_in_a_room_records_where_it_began_and_a_picture(self):
        manager, session_id, incident = self.run_session()
        row = self.wait_for(incident.clip_id)
        zone = self.clips.zones.zone("101")
        self.assertEqual(zone["total_falls"], 1)
        fall = zone["falls"][0]
        self.assertEqual((fall["fall_id"], fall["source_kind"]), (incident.clip_id, "live"))
        self.assertTrue(fall["onset_estimated"])
        self.assertAlmostEqual(fall["onset_x"], 160 / W, delta=0.1)
        self.assertEqual(row["room"], "101")
        self.assertTrue(self.clips.snapshot_path(row).is_file())
        manager.stop(session_id, "owner")

    def test_first_frame_with_nobody_in_it_becomes_the_room_photo(self):
        manager, session_id, _ = self.run_session()
        self.assertTrue(self.clips.zones.has_photo("101"))
        self.assertEqual(self.store.get_room_photo("101")["source"], "auto")
        manager.stop(session_id, "owner")

    def test_a_session_without_a_room_stores_no_zone_data_or_photo(self):
        manager, session_id, incident = self.run_session(room=None)
        self.wait_for(incident.clip_id)
        self.assertEqual(self.store.room_summaries(), [])
        self.assertEqual(self.store.room_photos(), [])
        manager.stop(session_id, "owner")

    def test_clip_reaches_back_to_the_start_of_the_models_four_second_window(self):
        manager, session_id, incident = self.run_session()
        row = self.wait_for(incident.clip_id)
        self.assertAlmostEqual(row["clip_start_seconds"], 0.167, delta=0.2)   # session began under 4 s earlier
        manager.stop(session_id, "owner")


@needs_encoder
class RecorderTimingTests(unittest.TestCase):
    """The clip must still contain the second after the fall when analysis stalls."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = Store(self.tmp / "db.sqlite3")
        self.clips = ClipManager(self.store, self.tmp / "clips", max_bytes=10**9, retention_seconds=86400.0,
                                 pre_seconds=4.0, post_seconds=1.0, max_per_job=10)
        self.addCleanup(self.clips.close)
        self.recorder = LiveClipRecorder(self.clips, "owner", "s")

    def feed(self, times):
        for t in times:
            self.recorder.add_frame(t, jpeg(int(t * 10) % 250))

    def wait(self, clip_id):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            row = self.store.get_clip(clip_id)
            if row["status"] != "pending":
                return row
            time.sleep(0.05)
        self.fail("clip stayed pending")

    def test_a_late_frame_still_closes_the_clip_with_something_after_the_fall(self):
        self.feed([i / 4 for i in range(0, 25)])          # 0 .. 6 s at 4 frames/s
        self.recorder.trigger(clip_id="c", track_id=1, detected_at=6.0, confidence=0.9)
        self.feed([7.6])                                   # analysis stalled: next frame is 1.6 s after the fall
        row = self.wait("c")
        self.assertEqual(row["status"], "ready")
        self.assertGreater(row["clip_start_seconds"] + row["duration_seconds"], 7.0)   # the second after the fall is in
        self.assertAlmostEqual(row["clip_start_seconds"], 2.0, delta=0.3)              # 4 s of lead-up

    def test_a_frame_far_past_the_window_ends_the_clip_without_being_added(self):
        self.feed([i / 4 for i in range(0, 25)])
        self.recorder.trigger(clip_id="c", track_id=1, detected_at=6.0, confidence=0.9)
        self.feed([12.0])
        row = self.wait("c")
        self.assertLess(row["clip_start_seconds"] + row["duration_seconds"], 6.6)

    def test_clip_is_saved_after_a_real_time_wait_if_the_camera_stops(self):
        self.feed([i / 4 for i in range(0, 25)])
        self.recorder.trigger(clip_id="c", track_id=1, detected_at=6.0, confidence=0.9)
        self.recorder.flush_due()
        self.assertEqual(self.store.get_clip("c")["status"], "pending")      # not yet: still waiting
        self.recorder._pending[0]["deadline"] = time.monotonic() - 1          # the wait is over
        self.recorder.flush_due()
        self.assertEqual(self.wait("c")["status"], "ready")


if __name__ == "__main__":
    unittest.main()
