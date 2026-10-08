"""API v1 integration tests.

Every engine here is a labelled TEST ADAPTER. Its numbers are not model output
and must never be presented as inference evidence.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import struct
import tempfile
import threading
import time
import unittest

from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app


def mp4_bytes(duration_seconds: float, padding: int = 0) -> bytes:
    """Smallest MP4 our validator accepts: ftyp box plus moov/mvhd duration."""

    ftyp = struct.pack(">I4s4sI4s", 20, b"ftyp", b"isom", 0, b"isom")
    timescale = 1000
    mvhd_payload = struct.pack(">IIIII", 0, 0, 0, timescale, int(duration_seconds * timescale))
    mvhd_payload += b"\0" * 80
    mvhd = struct.pack(">I4s", 8 + len(mvhd_payload), b"mvhd") + mvhd_payload
    moov = struct.pack(">I4s", 8 + len(mvhd), b"moov") + mvhd
    free = struct.pack(">I4s", 8 + padding, b"free") + b"\0" * padding if padding else b""
    return ftyp + moov + free


def pose(t: float) -> dict:
    return {
        "timestamp_seconds": t,
        "bbox_xyxy": [10.0, 20.0, 110.0, 220.0],
        "keypoints": [[50.0 + i, 60.0 + i, 0.9] for i in range(17)],
    }


class AdapterEngine:
    """TEST ADAPTER: emits scripted probabilities instead of running a model."""

    model_version = "test-adapter-not-a-model"

    def __init__(self, probabilities: list[float] | None = None) -> None:
        self.ready = True
        self.probabilities = probabilities or [0.1, 0.8, 0.9, 0.2, 0.2, 0.2, 0.7]
        self.gate: threading.Event | None = None  # set to hold a job in "running"
        self.error: Exception | None = None
        self.calls: list[Path] = []

    def analyze_video(self, video_path, *, on_pose, on_prediction, on_progress, cancel_event):
        self.calls.append(Path(video_path))
        if self.gate is not None:
            while not self.gate.wait(0.01):
                on_progress(0.5)  # raises inside the API when cancelled
        if self.error is not None:
            raise self.error
        for index, probability in enumerate(self.probabilities):
            t = 2.0 + 0.75 * index
            on_pose(pose(t))
            on_prediction({
                "timestamp_seconds": t, "fall_probability": probability,
                "window_start_seconds": t - 4, "source_pose_count": 24,
                "inference_ms": 30.0,
            })
            on_progress((index + 1) / len(self.probabilities))
        return {"duration_seconds": 8.0, "frame_width": 640, "frame_height": 480}

    def close(self) -> None:
        pass


class ApiTestCase(unittest.TestCase):
    engine_factory = AdapterEngine

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        examples = self.tmp / "examples"
        examples.mkdir()
        (examples / "fall.mp4").write_bytes(mp4_bytes(8))
        (examples / "catalog.json").write_text(json.dumps({"examples": [{
            "example_id": "fall-1", "title": "Fall example", "expected_outcome": "fall",
            "video_url": "/examples/fall.mp4", "duration_seconds": 8,
            "analysis_mode": "on_demand", "model_version": None,
            "provenance": "Test fixture, not an approved asset", "file": "fall.mp4",
        }]}))
        self.settings = Settings(
            data_dir=self.tmp / "data", examples_manifest=examples / "catalog.json",
            max_upload_bytes=200_000, job_timeout_seconds=5,
        )
        self.engine = self.engine_factory()
        self.app = create_app(self.settings, engine=self.engine)
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        if self.engine is not None and self.engine.gate is not None:
            self.engine.gate.set()
        self.client.__exit__(None, None, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def other_visitor(self) -> TestClient:
        return TestClient(self.app)  # shares the running app, separate cookie jar

    def upload(self, client: TestClient, data: bytes, name: str = "video.mp4"):
        return client.post("/api/v1/jobs/upload", files={"file": (name, data, "video/mp4")})

    def wait(self, client: TestClient, job_id: str, states=("completed", "failed", "cancelled")):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            job = client.get(f"/api/v1/jobs/{job_id}").json()
            if job["state"] in states:
                return job
            time.sleep(0.02)
        self.fail(f"job {job_id} never reached {states}")


class HealthAndExamplesTests(ApiTestCase):
    def test_health_ready_and_catalogue(self) -> None:
        self.assertEqual(self.client.get("/api/v1/health").json(), {"status": "ok"})
        ready = self.client.get("/api/v1/ready")
        self.assertEqual(ready.status_code, 200)
        examples = self.client.get("/api/v1/examples").json()["examples"]
        self.assertEqual([e["example_id"] for e in examples], ["fall-1"])
        self.assertNotIn("file", examples[0])  # no server paths leak

    def test_missing_catalogue_is_empty(self) -> None:
        self.settings.examples_manifest.unlink()
        self.assertEqual(self.client.get("/api/v1/examples").json(), {"examples": []})


class NoEngineTests(ApiTestCase):
    engine_factory = staticmethod(lambda: None)

    def test_no_engine_is_not_ready_and_refuses_jobs(self) -> None:
        self.assertEqual(self.client.get("/api/v1/ready").status_code, 503)
        response = self.upload(self.client, mp4_bytes(5))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "model_unavailable")
        response = self.client.post("/api/v1/jobs/example", json={"example_id": "fall-1"})
        self.assertEqual(response.status_code, 503)


class JobFlowTests(ApiTestCase):
    def test_example_job_completes_with_results_incidents_and_reports(self) -> None:
        created = self.client.post("/api/v1/jobs/example", json={"example_id": "fall-1"})
        self.assertEqual(created.status_code, 202)
        self.assertIn(created.json()["state"], ("queued", "running"))
        self.assertIsNone(created.json()["result_url"])

        job = self.wait(self.client, created.json()["job_id"])
        self.assertEqual(job["state"], "completed")
        self.assertEqual(job["progress"], 1.0)
        result = self.client.get(job["result_url"]).json()
        self.assertEqual(len(result["predictions"]), 7)
        self.assertEqual(len(result["poses"]), 7)
        self.assertEqual(result["frame_width"], 640)
        self.assertEqual(result["metrics"]["posec3d_calls"], 7)

        # 0.8 opens an incident; 0.9 is the same fall; three lows re-arm; 0.7 is new.
        incidents = result["incidents"]
        self.assertEqual([i["confidence"] for i in incidents], [0.8, 0.7])
        detail = self.client.get(
            f"/api/v1/jobs/{job['job_id']}/incidents/{incidents[0]['incident_id']}"
        )
        self.assertEqual(detail.json()["status"], "detected")

        csv_text = self.client.get(result["reports"]["csv"]).text
        self.assertEqual(csv_text.count(incidents[0]["incident_id"]), 1)
        self.assertEqual(self.client.get(result["reports"]["json"]).status_code, 200)
        media = self.client.get(result["media_url"], headers={"Range": "bytes=0-7"})
        self.assertEqual(media.status_code, 206)

    def test_results_are_409_until_complete(self) -> None:
        self.engine.gate = threading.Event()
        job_id = self.upload(self.client, mp4_bytes(5)).json()["job_id"]
        self.wait(self.client, job_id, ("running",))
        response = self.client.get(f"/api/v1/jobs/{job_id}/results")
        self.assertEqual(response.status_code, 409)
        self.engine.gate.set()
        self.assertEqual(self.wait(self.client, job_id)["state"], "completed")

    def test_engine_error_becomes_failed_job(self) -> None:
        error = RuntimeError("No person was visible.")
        error.code = "no_person"
        self.engine.error = error
        job_id = self.upload(self.client, mp4_bytes(5)).json()["job_id"]
        job = self.wait(self.client, job_id)
        self.assertEqual(job["state"], "failed")
        self.assertEqual(job["error"]["code"], "no_person")
        self.assertIsNone(job["result_url"])

    def test_invalid_engine_probability_is_rejected_not_clipped(self) -> None:
        self.engine.probabilities = [1.4]
        job = self.wait(self.client, self.upload(self.client, mp4_bytes(5)).json()["job_id"])
        self.assertEqual(job["error"]["code"], "invalid_engine_output")

    def test_cancel_running_job_then_delete(self) -> None:
        self.engine.gate = threading.Event()
        job_id = self.upload(self.client, mp4_bytes(5)).json()["job_id"]
        self.wait(self.client, job_id, ("running",))
        self.assertEqual(self.client.delete(f"/api/v1/jobs/{job_id}").status_code, 200)
        self.assertEqual(self.wait(self.client, job_id)["state"], "cancelled")
        self.assertEqual(self.client.delete(f"/api/v1/jobs/{job_id}").status_code, 204)
        self.assertEqual(self.client.get(f"/api/v1/jobs/{job_id}").status_code, 404)
        self.assertFalse((self.settings.data_dir / "jobs" / job_id).exists())

    def test_cancel_queued_job_never_runs(self) -> None:
        self.engine.gate = threading.Event()
        first = self.upload(self.client, mp4_bytes(5)).json()["job_id"]
        self.wait(self.client, first, ("running",))
        second = self.upload(self.client, mp4_bytes(5)).json()["job_id"]
        self.client.delete(f"/api/v1/jobs/{second}")
        self.assertEqual(self.client.get(f"/api/v1/jobs/{second}").json()["state"], "cancelled")
        self.engine.gate.set()
        self.wait(self.client, first)
        self.assertEqual(len(self.engine.calls), 1)

    def test_timeout_fails_job(self) -> None:
        self.app.state.runner.timeout_seconds = 0.1
        self.engine.gate = threading.Event()  # never released before the timeout
        job = self.wait(self.client, self.upload(self.client, mp4_bytes(5)).json()["job_id"])
        self.assertEqual(job["error"]["code"], "timeout")


class IsolationAndAccessTests(ApiTestCase):
    def test_two_visitors_same_filename_are_isolated(self) -> None:
        visitor_b = self.other_visitor()
        a = self.upload(self.client, mp4_bytes(5, padding=10), "clip.mp4").json()
        b = self.upload(visitor_b, mp4_bytes(6, padding=20), "clip.mp4").json()
        self.assertNotEqual(a["job_id"], b["job_id"])
        self.wait(self.client, a["job_id"])
        self.wait(visitor_b, b["job_id"])
        # Each job analysed its own file; neither overwrote the other.
        self.assertEqual(len(set(self.engine.calls)), 2)
        a_media = self.client.get(f"/api/v1/jobs/{a['job_id']}/media").content
        b_media = visitor_b.get(f"/api/v1/jobs/{b['job_id']}/media").content
        self.assertEqual(a_media, mp4_bytes(5, padding=10))
        self.assertEqual(b_media, mp4_bytes(6, padding=20))

    def test_other_visitor_cannot_see_or_cancel_a_job(self) -> None:
        job = self.wait(self.client, self.upload(self.client, mp4_bytes(5)).json()["job_id"])
        result = self.client.get(job["result_url"]).json()
        intruder = self.other_visitor()
        base = f"/api/v1/jobs/{job['job_id']}"
        paths = [base, f"{base}/results", f"{base}/media", f"{base}/reports/json",
                 f"{base}/reports/csv",
                 f"{base}/incidents/{result['incidents'][0]['incident_id']}"]
        for path in paths:
            self.assertEqual(intruder.get(path).status_code, 404, path)
        self.assertEqual(intruder.delete(base).status_code, 404)
        self.assertEqual(self.client.get(base).status_code, 200)

    def test_cross_site_origin_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/jobs/example", json={"example_id": "fall-1"},
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(response.status_code, 403)
        same_site = self.client.post(
            "/api/v1/jobs/example", json={"example_id": "fall-1"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(same_site.status_code, 202)

    def test_session_cookie_is_httponly_and_strict(self) -> None:
        response = self.client.post("/api/v1/jobs/example", json={"example_id": "fall-1"})
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)


class UploadLimitTests(ApiTestCase):
    def test_rejects_non_mp4_content_even_with_mp4_name(self) -> None:
        response = self.upload(self.client, b"not a video at all", "fake.mp4")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_video")

    def test_rejects_too_long_and_too_large(self) -> None:
        self.assertEqual(self.upload(self.client, mp4_bytes(61)).status_code, 400)
        big = mp4_bytes(5, padding=self.settings.max_upload_bytes)
        self.assertEqual(self.upload(self.client, big).status_code, 413)
        leftover = list((self.settings.data_dir / "jobs").iterdir())
        self.assertEqual(leftover, [])  # rejected uploads leave no files

    def test_queue_capacity_returns_429(self) -> None:
        self.engine.gate = threading.Event()
        running = self.upload(self.client, mp4_bytes(5)).json()["job_id"]
        self.wait(self.client, running, ("running",))
        for _ in range(self.settings.max_queued_jobs):
            self.assertEqual(self.upload(self.client, mp4_bytes(5)).status_code, 202)
        response = self.upload(self.client, mp4_bytes(5))
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "capacity")

    def test_unknown_example_is_404(self) -> None:
        response = self.client.post("/api/v1/jobs/example", json={"example_id": "nope"})
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
