"""Bounded job execution: one inference job at a time on one worker thread.

Heavy inference never runs in the request handler. Each job gets its own
tracker, record lists and cancel event, so nothing carries across jobs.
"""
from __future__ import annotations

from collections import deque
import logging
from pathlib import Path
import secrets
import threading
from time import monotonic
from typing import Any, Mapping

from pydantic import ValidationError

from icare.api.engine import Engine
from icare.api.incidents import PersonIncidents
from icare.api.results import ResultTooLarge, build_result, write_outputs
from icare.api.schemas import Pose, Prediction
from icare.api.store import Store, utc_now


log = logging.getLogger(__name__)


class JobCancelled(Exception):
    pass


class InvalidEngineOutput(Exception):
    code = "invalid_engine_output"


class JobRunner:
    def __init__(
        self, store: Store, engine: Engine | None, jobs_dir: Path, timeout_seconds: float,
        max_result_bytes: int = 16 * 1024 * 1024, fall_confirmations: int = 1, clips=None,
    ) -> None:
        self.store = store
        self.clips = clips  # icare.api.clips.ClipManager, or None to keep no fall clips
        self.engine = engine
        self.jobs_dir = jobs_dir
        self.timeout_seconds = timeout_seconds
        self.max_result_bytes = max_result_bytes
        self.fall_confirmations = fall_confirmations
        self._pending: deque[str] = deque()
        self._wake = threading.Condition()
        self._cancel_events: dict[str, threading.Event] = {}
        self._stopping = False
        self._timed_out = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="icare-job-worker", daemon=True)

    def start(self) -> None:
        self._thread.start()

    @property
    def available(self) -> bool:
        """An unresponsive timed-out engine must not accept more work."""
        return not self._timed_out.is_set()

    def stop(self) -> None:
        with self._wake:
            self._stopping = True
            for event in self._cancel_events.values():
                event.set()
            self._wake.notify_all()
        self._thread.join(timeout=10)

    def submit(self, job_id: str) -> None:
        with self._wake:
            self._pending.append(job_id)
            self._wake.notify()

    def cancel(self, job_id: str) -> None:
        """Cancel a queued job now, or ask a running job's engine to stop."""

        if self.store.transition(job_id, ("queued",), state="cancelled", progress=None):
            return
        with self._wake:
            event = self._cancel_events.get(job_id)
        if event is not None:
            event.set()

    def _loop(self) -> None:
        while True:
            with self._wake:
                while not self._pending and not self._stopping:
                    self._wake.wait()
                if self._stopping:
                    return
                job_id = self._pending.popleft()
                cancel_event = threading.Event()
                self._cancel_events[job_id] = cancel_event
            try:
                self._run(job_id, cancel_event)
            except Exception:  # noqa: BLE001 - the worker thread must survive
                log.exception("Unexpected worker failure for job %s", job_id)
                self.store.transition(
                    job_id, ("queued", "running"), state="failed", progress=None,
                    error_code="internal_error", error_message="The job failed unexpectedly.",
                )
            finally:
                with self._wake:
                    self._cancel_events.pop(job_id, None)
                    self._timed_out.clear()

    def _run(self, job_id: str, cancel_event: threading.Event) -> None:
        if not self.store.transition(job_id, ("queued",), state="running", progress=None):
            return  # cancelled while it waited in the queue
        job = self.store.get_job(job_id)
        assert job is not None and self.engine is not None
        job_dir = self.jobs_dir / job_id

        timed_out = threading.Event()

        def on_timeout() -> None:
            with self._wake:
                if self._cancel_events.get(job_id) is not cancel_event:
                    return  # Late timer callback after the job was released.
                timed_out.set()
                cancel_event.set()
                self._timed_out.set()
                self._fail(job_id, "timeout", "Analysis took longer than the time limit.")

        timer = threading.Timer(self.timeout_seconds, on_timeout)
        timer.daemon = True

        incidents_by_person = PersonIncidents(confirmations=self.fall_confirmations)
        predictions: list[dict[str, Any]] = []
        poses: list[dict[str, Any]] = []
        incidents: list[dict[str, Any]] = []

        def on_pose(record: Mapping[str, Any]) -> None:
            poses.append(_validated(Pose, record))

        def on_prediction(record: Mapping[str, Any]) -> None:
            prediction = _validated(Prediction, record)
            predictions.append(prediction)
            # Each person has an independent incident rule; legacy engines without
            # track IDs are treated as one person (0), the previous behaviour.
            person = prediction["track_id"] or 0
            if incidents_by_person.observe(person, prediction["fall_probability"]):
                incident = {
                    "incident_id": secrets.token_urlsafe(8),
                    "job_id": job_id,
                    "track_id": prediction["track_id"],
                    "detected_at_seconds": prediction["timestamp_seconds"],
                    "confidence": prediction["fall_probability"],
                    "status": "detected",
                    "created_at_utc": utc_now(),
                }
                incidents.append(incident)

        def on_progress(value: float | None) -> None:
            if cancel_event.is_set():
                raise JobCancelled
            # 1.0 is reserved for "results written", so cap engine progress below it.
            progress = None if value is None else min(max(float(value), 0.0), 0.99)
            self.store.update_job(job_id, progress=progress)

        started = monotonic()
        timer.start()
        try:
            if hasattr(self.engine, 'wait_ready'):
                self.engine.wait_ready(cancel_event)
            summary = self.engine.analyze_video(
                Path(job["media_path"]),
                on_pose=on_pose,
                on_prediction=on_prediction,
                on_progress=on_progress,
                cancel_event=cancel_event,
            )
        except JobCancelled:
            summary = None
        except Exception as exc:  # noqa: BLE001 - every engine failure becomes a job error
            if not cancel_event.is_set():
                code = getattr(exc, "code", None)
                self._fail(
                    job_id,
                    code if isinstance(code, str) else "engine_error",
                    str(exc) or "The model could not analyse this video.",
                )
                return
            summary = None
        finally:
            timer.cancel()

        if timed_out.is_set():
            self._fail(job_id, "timeout", "Analysis took longer than the time limit.")
            return
        if cancel_event.is_set() or summary is None:
            self.store.transition(job_id, ("running",), state="cancelled", progress=None)
            return

        room = job.get("room")
        locations: dict[str, dict[str, Any]] = {}
        if self.clips is not None and incidents:
            # Cut before the result is written so each incident carries its clip_id.
            try:
                locations = self.clips.locate_falls(
                    poses, incidents, int(summary["frame_width"]), int(summary["frame_height"]))
            except (KeyError, TypeError, ValueError):
                log.exception("Could not locate falls for job %s", job_id)
            self.clips.cut_from_video(
                job["owner"], job_id, Path(job["media_path"]), incidents,
                _number(summary.get("duration_seconds")), cancel_event, room=room, locations=locations,
            )
            if cancel_event.is_set():
                self._drop_clips(job_id)
                self.store.transition(job_id, ("running",), state="cancelled", progress=None)
                return

        try:
            result = build_result(
                job_id, summary, self.engine.model_version,
                predictions, poses, incidents, monotonic() - started,
            )
        except (KeyError, TypeError, ValueError):
            self._drop_clips(job_id)
            self._fail(job_id, "invalid_engine_output", "The engine summary was incomplete.")
            return
        try:
            write_outputs(job_dir, result, self.max_result_bytes)
        except ResultTooLarge:
            self._drop_clips(job_id)
            self._fail(job_id, 'result_too_large', 'The analysis exceeded its result storage budget.')
            return
        for incident in incidents:
            self.store.add_incident(incident)
        if not self.store.transition(
            job_id, ("running",), state="completed", progress=1.0,
            model_version=self.engine.model_version,
        ):
            self.store.clear_incidents(job_id)  # cancelled during the final write
            self._drop_clips(job_id)
            return
        if self.clips is not None and room:
            # Only completed jobs feed the room's danger zone, which outlives the clips.
            try:
                self.clips.record_locations(room, "upload", job_id, incidents, locations)
                self.clips.reference_photo_from_video(
                    room, Path(job["media_path"]), [pose["timestamp_seconds"] for pose in poses])
            except Exception:  # noqa: BLE001 - the finished job must not fail because of this
                log.exception("Could not update the danger zone of room %s", room)

    def _drop_clips(self, job_id: str) -> None:
        if self.clips is not None:
            self.clips.delete_for_source(job_id)

    def _fail(self, job_id: str, code: str, message: str) -> None:
        self.store.transition(
            job_id, ("running",), state="failed", progress=None,
            error_code=code, error_message=message,
        )


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _validated(model, record: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return model.model_validate(dict(record)).model_dump()
    except ValidationError as exc:
        raise InvalidEngineOutput(f"Engine produced an invalid {model.__name__} record.") from exc
