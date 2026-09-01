from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Protocol

import cv2
import numpy as np


@dataclass(frozen=True)
class ModelOutput:
    """One temporal-window prediction from the binary PoseC3D model."""

    timestamp_seconds: float
    fall_probability: float


@dataclass
class FallEvent:
    event_id: int
    start_seconds: float
    end_seconds: float | None
    peak_confidence: float
    source: str
    created_at_utc: str

    @property
    def duration_seconds(self) -> float | None:
        if self.end_seconds is None:
            return None
        return round(self.end_seconds - self.start_seconds, 3)

    def as_report_dict(self) -> dict:
        result = asdict(self)
        result["duration_seconds"] = self.duration_seconds
        return result


class InferenceBackend(Protocol):
    """Boundary implemented later by pose extraction + fine-tuned PoseC3D."""

    @property
    def available(self) -> bool: ...

    @property
    def name(self) -> str: ...

    def reset(self) -> None: ...

    def process_frame(
        self, frame_rgb: np.ndarray, timestamp_seconds: float
    ) -> ModelOutput | None: ...


class UnconfiguredBackend:
    """Safe placeholder that never fabricates model predictions."""

    available = False
    name = "Model pending"

    def reset(self) -> None:
        return None

    def process_frame(
        self, frame_rgb: np.ndarray, timestamp_seconds: float
    ) -> ModelOutput | None:
        del frame_rgb, timestamp_seconds
        return None


class FallDetectionSession:
    def __init__(
        self,
        backend: InferenceBackend,
        fall_threshold: float = 0.65,
        clear_threshold: float = 0.45,
        confirmation_windows: int = 2,
        clear_windows: int = 3,
    ) -> None:
        self.backend = backend
        self.fall_threshold = fall_threshold
        self.clear_threshold = clear_threshold
        self.confirmation_windows = confirmation_windows
        self.clear_windows = clear_windows
        self.lock = Lock()
        self.reset("webcam")

    def reset(self, source: str) -> None:
        with getattr(self, "lock", Lock()):
            self.source = source
            self.started_at_utc = datetime.now(timezone.utc).isoformat()
            self.started_monotonic = monotonic()
            self.frames_seen = 0
            self.latest_output: ModelOutput | None = None
            self.max_fall_probability = 0.0
            self.positive_windows = 0
            self.clear_count = 0
            self.positive_start_seconds: float | None = None
            self.active_event: FallEvent | None = None
            self.events: list[FallEvent] = []
            self.backend.reset()

    def process(
        self, frame_rgb: np.ndarray, timestamp_seconds: float | None = None
    ) -> np.ndarray:
        with self.lock:
            if timestamp_seconds is None:
                timestamp_seconds = monotonic() - self.started_monotonic
            self.frames_seen += 1
            output = self.backend.process_frame(frame_rgb, timestamp_seconds)
            if output is not None:
                self._consume_output(output)
            annotate = getattr(self.backend, "annotate_frame", None)
            if annotate is not None:
                frame_rgb = annotate(frame_rgb)
            return self._overlay(frame_rgb, timestamp_seconds)

    def _consume_output(self, output: ModelOutput) -> None:
        probability = float(np.clip(output.fall_probability, 0.0, 1.0))
        self.latest_output = ModelOutput(output.timestamp_seconds, probability)
        self.max_fall_probability = max(self.max_fall_probability, probability)

        if probability >= self.fall_threshold:
            self.clear_count = 0
            if self.positive_windows == 0:
                self.positive_start_seconds = output.timestamp_seconds
            self.positive_windows += 1

            if self.active_event is None and self.positive_windows >= self.confirmation_windows:
                self.active_event = FallEvent(
                    event_id=len(self.events) + 1,
                    start_seconds=round(
                        self.positive_start_seconds or output.timestamp_seconds, 3
                    ),
                    end_seconds=None,
                    peak_confidence=round(probability, 4),
                    source=self.source,
                    created_at_utc=datetime.now(timezone.utc).isoformat(),
                )
                self.events.append(self.active_event)
            elif self.active_event is not None:
                self.active_event.peak_confidence = round(
                    max(self.active_event.peak_confidence, probability), 4
                )
            return

        if self.active_event is not None:
            self.positive_windows = 0
            self.positive_start_seconds = None
            if probability < self.clear_threshold:
                self.clear_count += 1
                if self.clear_count >= self.clear_windows:
                    self.active_event.end_seconds = round(output.timestamp_seconds, 3)
                    self.active_event = None
                    self.clear_count = 0
            else:
                # Hysteresis: an active event remains active between the clear
                # and trigger thresholds instead of flickering off immediately.
                self.clear_count = 0
            return

        self.positive_windows = 0
        self.positive_start_seconds = None

    def inject_demo_event(self) -> None:
        """UI-only preview; explicitly marked as simulated in the report."""

        with self.lock:
            start = max(0.0, monotonic() - self.started_monotonic)
            self.events.append(
                FallEvent(
                    event_id=len(self.events) + 1,
                    start_seconds=round(start, 3),
                    end_seconds=round(start + 2.5, 3),
                    peak_confidence=0.91,
                    source="simulated preview",
                    created_at_utc=datetime.now(timezone.utc).isoformat(),
                )
            )
            self.max_fall_probability = max(self.max_fall_probability, 0.91)

    def snapshot(self) -> dict:
        with self.lock:
            probability = (
                self.latest_output.fall_probability if self.latest_output else None
            )
            return {
                "state": self._state_unlocked(),
                "source": self.source,
                "model": self.backend.name,
                "model_available": self.backend.available,
                "started_at_utc": self.started_at_utc,
                "current_fall_probability": (
                    round(probability, 4) if probability is not None else None
                ),
                "maximum_fall_probability": round(self.max_fall_probability, 4),
                "events": [event.as_report_dict() for event in self.events],
            }

    def _state_unlocked(self) -> str:
        if not self.backend.available:
            return "Model not connected"
        if self.active_event is not None:
            return "Fall detected"
        if self.latest_output is None:
            return "Preparing"
        if self.latest_output.fall_probability >= self.fall_threshold:
            return "Checking possible fall"
        return "No fall detected"

    def _overlay(self, frame_rgb: np.ndarray, timestamp_seconds: float) -> np.ndarray:
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        state = self._state_unlocked()
        color = (40, 210, 70)
        if state == "Fall detected":
            color = (35, 35, 245)
        elif state in {"Model not connected", "Checking possible fall"}:
            color = (0, 190, 255)
        elif state == "Preparing":
            color = (245, 145, 30)
        cv2.rectangle(frame_bgr, (14, 14), (470, 102), color, -1)
        cv2.rectangle(frame_bgr, (14, 14), (470, 102), (255, 255, 255), 2)
        cv2.putText(
            frame_bgr,
            state.upper(),
            (28, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.88,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame_bgr,
            f"{timestamp_seconds:0.1f} s",
            (28, 86),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            2,
        )
        return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
