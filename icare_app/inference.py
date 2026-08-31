from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Protocol

import cv2
import numpy as np


ACTIVITY_NAMES = {
    1: "Falling forward using hands",
    2: "Falling forward using knees",
    3: "Falling backwards",
    4: "Falling sideward",
    5: "Falling sitting in empty chair",
    6: "Walking",
    7: "Standing",
    8: "Sitting",
    9: "Picking up an object",
    10: "Jumping",
    11: "Laying",
}


@dataclass(frozen=True)
class ModelOutput:
    timestamp_seconds: float
    activity_id: int
    activity_probabilities: list[float]

    @property
    def activity_name(self) -> str:
        return ACTIVITY_NAMES.get(self.activity_id, "Unknown")

    @property
    def fall_probability(self) -> float:
        return float(sum(self.activity_probabilities[:5]))


@dataclass(frozen=True)
class FallEvent:
    event_id: int
    timestamp_seconds: float
    confidence: float
    activity_id: int
    activity_name: str
    source: str
    created_at_utc: str


class InferenceBackend(Protocol):
    """The contract the future RTMPose + PoseC3D implementation must satisfy."""

    @property
    def available(self) -> bool: ...

    @property
    def name(self) -> str: ...

    def reset(self) -> None: ...

    def process_frame(self, frame_rgb: np.ndarray, timestamp_seconds: float) -> ModelOutput | None: ...


class UnconfiguredBackend:
    """Safe placeholder: it never fabricates an inference result."""

    available = False
    name = "RTMPose + PoseC3D (not configured)"

    def reset(self) -> None:
        return None

    def process_frame(self, frame_rgb: np.ndarray, timestamp_seconds: float) -> ModelOutput | None:
        del frame_rgb, timestamp_seconds
        return None


class FallDetectionSession:
    def __init__(
        self,
        backend: InferenceBackend,
        fall_threshold: float = 0.70,
        confirmation_windows: int = 3,
        cooldown_seconds: float = 8.0,
    ) -> None:
        self.backend = backend
        self.fall_threshold = fall_threshold
        self.confirmation_windows = confirmation_windows
        self.cooldown_seconds = cooldown_seconds
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
            self.last_event_timestamp = -float("inf")
            self.events: list[FallEvent] = []
            self.backend.reset()

    def process(self, frame_rgb: np.ndarray, timestamp_seconds: float | None = None) -> np.ndarray:
        with self.lock:
            if timestamp_seconds is None:
                timestamp_seconds = monotonic() - self.started_monotonic
            self.frames_seen += 1
            output = self.backend.process_frame(frame_rgb, timestamp_seconds)
            if output is not None:
                self._consume_output(output)
            return self._overlay(frame_rgb, timestamp_seconds)

    def _consume_output(self, output: ModelOutput) -> None:
        self.latest_output = output
        probability = output.fall_probability
        self.max_fall_probability = max(self.max_fall_probability, probability)
        self.positive_windows = self.positive_windows + 1 if probability >= self.fall_threshold else 0

        confirmed = self.positive_windows >= self.confirmation_windows
        outside_cooldown = output.timestamp_seconds - self.last_event_timestamp >= self.cooldown_seconds
        if confirmed and outside_cooldown:
            self._append_event(
                timestamp_seconds=output.timestamp_seconds,
                confidence=probability,
                activity_id=output.activity_id,
                activity_name=output.activity_name,
                source=self.source,
            )
            self.last_event_timestamp = output.timestamp_seconds
            self.positive_windows = 0

    def inject_demo_event(self) -> None:
        with self.lock:
            timestamp = monotonic() - self.started_monotonic
            self._append_event(timestamp, 0.91, 3, ACTIVITY_NAMES[3], "demo injection")
            self.max_fall_probability = max(self.max_fall_probability, 0.91)

    def _append_event(
        self,
        timestamp_seconds: float,
        confidence: float,
        activity_id: int,
        activity_name: str,
        source: str,
    ) -> None:
        self.events.append(
            FallEvent(
                event_id=len(self.events) + 1,
                timestamp_seconds=round(float(timestamp_seconds), 3),
                confidence=round(float(confidence), 4),
                activity_id=activity_id,
                activity_name=activity_name,
                source=source,
                created_at_utc=datetime.now(timezone.utc).isoformat(),
            )
        )

    def snapshot(self) -> dict:
        with self.lock:
            output = self.latest_output
            if not self.backend.available:
                state = "MODEL NOT CONFIGURED"
            elif self.events:
                state = "FALL DETECTED"
            elif output is None:
                state = "COLLECTING MOTION CONTEXT"
            elif output.fall_probability >= self.fall_threshold:
                state = "POSSIBLE FALL"
            else:
                state = "NORMAL"

            return {
                "state": state,
                "source": self.source,
                "backend": self.backend.name,
                "backend_available": self.backend.available,
                "started_at_utc": self.started_at_utc,
                "frames_seen": self.frames_seen,
                "latest_activity": output.activity_name if output else "Unavailable",
                "latest_fall_probability": round(output.fall_probability, 4) if output else None,
                "max_fall_probability": round(self.max_fall_probability, 4),
                "confirmation_progress": f"{self.positive_windows}/{self.confirmation_windows}",
                "events": [asdict(event) for event in self.events],
            }

    def _overlay(self, frame_rgb: np.ndarray, timestamp_seconds: float) -> np.ndarray:
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        snapshot = self.snapshot_unlocked()
        color = (50, 205, 50)
        if snapshot["state"] == "FALL DETECTED":
            color = (40, 40, 230)
        elif snapshot["state"] in {"MODEL NOT CONFIGURED", "POSSIBLE FALL"}:
            color = (0, 180, 255)
        cv2.rectangle(frame_bgr, (12, 12), (520, 112), (25, 25, 25), -1)
        cv2.putText(frame_bgr, snapshot["state"], (28, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
        cv2.putText(frame_bgr, f"Time: {timestamp_seconds:0.1f}s", (28, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (235, 235, 235), 1)
        cv2.putText(frame_bgr, f"Activity: {snapshot['latest_activity']}", (28, 103), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (235, 235, 235), 1)
        return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    def snapshot_unlocked(self) -> dict:
        output = self.latest_output
        if not self.backend.available:
            state = "MODEL NOT CONFIGURED"
        elif self.events:
            state = "FALL DETECTED"
        elif output is None:
            state = "COLLECTING MOTION CONTEXT"
        elif output.fall_probability >= self.fall_threshold:
            state = "POSSIBLE FALL"
        else:
            state = "NORMAL"
        return {
            "state": state,
            "latest_activity": output.activity_name if output else "Unavailable",
        }

