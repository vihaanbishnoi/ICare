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

from api.engine import Engine
from api.incidents import IncidentTracker
from api.results import build_result, write_outputs
from api.schemas import Pose, Prediction
from api.store import Store, utc_now


log = logging.getLogger(__name__)


class JobCancelled(Exception):
    pass


class InvalidEngineOutput(Exception):
    code = "invalid_engine_output"


class JobRunner:
    def __init__(
        self, store: Store, engine: Engine | None, jobs_dir: Path, timeout_seconds: float
    ) -> None:
        self.store = store
        self.engine = engine
        self.jobs_dir = jobs_dir
        self.timeout_seconds = timeout_seconds
        self._pending: deque[str] = deque()
        self._wake = threading.Condition()
        self._cancel_events: dict[str, threading.Event] = {}
        self._stopping = False
        self._thread = threading.Thread(target=self._loop, name="icare-job-worker", daemon=True)

    def start(self) -> None:
        self._thread.start()

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

    def _run(self, job_id: str, cancel_event: threading.Event) -> None:
        if not self.store.transition(job_id, ("queued",), state="running", progress=None):
            return  # cancelled while it waited in the queue
        job = self.store.get_job(job_id)
        assert job is not None and self.engine is not None
        job_dir = self.jobs_dir / job_id

        timed_out = threading.Event()

        def on_timeout() -> None:
            timed_out.set()
            cancel_event.set()

        timer = threading.Timer(self.timeout_seconds, on_timeout)
        timer.daemon = True

        tracker = IncidentTracker()
        predictions: list[dict[str, Any]] = []
        poses: list[dict[str, Any]] = []
        incidents: list[dict[str, Any]] = []

        def on_pose(record: Mapping[str, Any]) -> None:
            poses.append(_validated(Pose, record))

        def on_prediction(record: Mapping[str, Any]) -> None:
            prediction = _validated(Prediction, record)
            predictions.append(prediction)
            if tracker.observe(prediction["fall_probability"]):
                incident = {
                    "incident_id": secrets.token_urlsafe(8),
                    "job_id": job_id,
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

        try:
            result = build_result(
                job_id, summary, self.engine.model_version,
                predictions, poses, incidents, monotonic() - started,
            )
        except (KeyError, TypeError, ValueError):
            self._fail(job_id, "invalid_engine_output", "The engine summary was incomplete.")
            return
        write_outputs(job_dir, result)
        for incident in incidents:
            self.store.add_incident(incident)
        if not self.store.transition(
            job_id, ("running",), state="completed", progress=1.0,
            model_version=self.engine.model_version,
        ):
            self.store.clear_incidents(job_id)  # cancelled during the final write

    def _fail(self, job_id: str, code: str, message: str) -> None:
        self.store.transition(
            job_id, ("running",), state="failed", progress=None,
            error_code=code, error_message=message,
        )


def _validated(model, record: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return model.model_validate(dict(record)).model_dump()
    except ValidationError as exc:
        raise InvalidEngineOutput(f"Engine produced an invalid {model.__name__} record.") from exc
