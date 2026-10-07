from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class ModelOutput:
    """One temporal-window prediction from the binary PoseC3D model."""

    timestamp_seconds: float
    fall_probability: float
    inference_ms: float | None = None
    window_start_seconds: float | None = None
    source_pose_count: int | None = None
    urgency: float | None = None
    reliability: float | None = None
    process_cpu_percent: float | None = None
    process_rss_mb: float | None = None


@dataclass
class FallEvent:
    event_id: int
    detected_at_seconds: float
    confidence: float
    source: str
    created_at_utc: str
    fall_onset_seconds: float | None = None
    alert_latency_seconds: float | None = None

    def as_report_dict(self) -> dict:
        return asdict(self)


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
        fall_threshold: float = 0.50,
        clear_threshold: float = 0.35,
        clear_windows: int = 3,
        ground_truth: str = "unknown",
        fall_onset_seconds: float | None = None,
    ) -> None:
        self.backend = backend
        self.fall_threshold = fall_threshold
        self.clear_threshold = clear_threshold
        self.clear_windows = clear_windows
        self.ground_truth = self._normalize_ground_truth(ground_truth)
        self.fall_onset_seconds = (
            self._normalize_onset(fall_onset_seconds)
            if self.ground_truth == "fall"
            else None
        )
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
            self.inference_records: list[dict] = []
            self.analysis_complete = False
            self.clear_count = 0
            self.armed = True
            self.events: list[FallEvent] = []
            self.backend.reset()

    def configure_evaluation(
        self,
        ground_truth: str = "unknown",
        fall_onset_seconds: float | None = None,
    ) -> None:
        with self.lock:
            self.ground_truth = self._normalize_ground_truth(ground_truth)
            self.fall_onset_seconds = (
                self._normalize_onset(fall_onset_seconds)
                if self.ground_truth == "fall"
                else None
            )

    def mark_complete(self) -> None:
        with self.lock:
            self.analysis_complete = True

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
        self.latest_output = ModelOutput(
            timestamp_seconds=output.timestamp_seconds,
            fall_probability=probability,
            inference_ms=output.inference_ms,
            window_start_seconds=output.window_start_seconds,
            source_pose_count=output.source_pose_count,
            urgency=output.urgency,
            reliability=output.reliability,
            process_cpu_percent=output.process_cpu_percent,
            process_rss_mb=output.process_rss_mb,
        )
        self.max_fall_probability = max(self.max_fall_probability, probability)
        self.inference_records.append(
            {
                "timestamp_seconds": round(float(output.timestamp_seconds), 6),
                "fall_probability": round(probability, 6),
                "inference_ms": self._round_optional(output.inference_ms),
                "window_start_seconds": self._round_optional(
                    output.window_start_seconds
                ),
                "source_pose_count": output.source_pose_count,
                "urgency": self._round_optional(output.urgency),
                "reliability": self._round_optional(output.reliability),
                "process_cpu_percent": self._round_optional(
                    output.process_cpu_percent
                ),
                "process_rss_mb": self._round_optional(output.process_rss_mb),
            }
        )

        if self.armed and probability >= self.fall_threshold:
            alert_latency = None
            if self.fall_onset_seconds is not None:
                alert_latency = max(
                    0.0, output.timestamp_seconds - self.fall_onset_seconds
                )
            event = FallEvent(
                event_id=len(self.events) + 1,
                detected_at_seconds=round(output.timestamp_seconds, 3),
                confidence=round(probability, 4),
                source=self.source,
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                fall_onset_seconds=self.fall_onset_seconds,
                alert_latency_seconds=(
                    round(alert_latency, 3) if alert_latency is not None else None
                ),
            )
            self.events.append(event)
            self.armed = False
            self.clear_count = 0
            return

        if not self.armed:
            if probability < self.clear_threshold:
                self.clear_count += 1
                if self.clear_count >= self.clear_windows:
                    self.armed = True
                    self.clear_count = 0
            else:
                self.clear_count = 0

    def inject_demo_event(self) -> None:
        """UI-only preview; explicitly marked as simulated in the report."""

        with self.lock:
            start = max(0.0, monotonic() - self.started_monotonic)
            self.events.append(
                FallEvent(
                    event_id=len(self.events) + 1,
                    detected_at_seconds=round(start, 3),
                    confidence=0.91,
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
            runtime_snapshot = getattr(self.backend, "runtime_snapshot", None)
            backend_metrics = runtime_snapshot() if runtime_snapshot else {}
            inference_times = [
                record["inference_ms"]
                for record in self.inference_records
                if record["inference_ms"] is not None
            ]
            alert_latencies = [
                event.alert_latency_seconds
                for event in self.events
                if event.alert_latency_seconds is not None
            ]
            false_alarm_count = (
                len(self.events) if self.ground_truth == "no_fall" else None
            )
            missed_fall = (
                self.analysis_complete
                and self.ground_truth == "fall"
                and not self.events
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
                "ground_truth": self.ground_truth,
                "fall_onset_seconds": self.fall_onset_seconds,
                "analysis_complete": self.analysis_complete,
                "evaluation": {
                    "posec3d_calls": len(self.inference_records),
                    "mean_posec3d_inference_ms": self._mean(inference_times),
                    "median_posec3d_inference_ms": self._median(inference_times),
                    "mean_alert_latency_seconds": self._mean(alert_latencies),
                    "false_alarm_count": false_alarm_count,
                    "missed_fall": missed_fall,
                    **backend_metrics,
                },
                "inference_records": list(self.inference_records),
                "events": [event.as_report_dict() for event in self.events],
            }

    @staticmethod
    def _normalize_ground_truth(value: str) -> str:
        normalized = str(value).strip().lower().replace(" ", "_")
        return normalized if normalized in {"fall", "no_fall"} else "unknown"

    @staticmethod
    def _normalize_onset(value: float | None) -> float | None:
        if value is None:
            return None
        numeric = float(value)
        return numeric if numeric >= 0 else None

    @staticmethod
    def _round_optional(value: float | None) -> float | None:
        return None if value is None else round(float(value), 6)

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        return None if not values else round(float(np.mean(values)), 6)

    @staticmethod
    def _median(values: list[float]) -> float | None:
        return None if not values else round(float(np.median(values)), 6)

    def _state_unlocked(self) -> str:
        if not self.backend.available:
            return "Model not connected"
        if not self.armed:
            return "Fall detected"
        if self.latest_output is None:
            return "Preparing"
        return "No fall detected"

    def _overlay(self, frame_rgb: np.ndarray, timestamp_seconds: float) -> np.ndarray:
        import cv2

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
