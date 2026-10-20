"""Engine boundary injected into the job worker.

The production adapter loads icare.inference.engine in an isolated process.
The API never imports pose/ONNX code directly, and it never substitutes a fake
engine: when no real engine loads, /ready and job creation return 503.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
import threading
from typing import Any, Callable, Mapping, Protocol

from icare.api.config import ROOT


log = logging.getLogger(__name__)

PoseCallback = Callable[[Mapping[str, Any]], None]
PredictionCallback = Callable[[Mapping[str, Any]], None]
ProgressCallback = Callable[[float | None], None]


class Engine(Protocol):
    """What the API expects from load_engine(config).

    analyze_video calls on_pose/on_prediction with records using the field names
    in src/icare/api/schemas.py, and returns a summary only after the final
    prediction has been emitted. The summary must include duration_seconds,
    frame_width and frame_height of the original source video.

    Failures are raised as exceptions. An optional string attribute ``code``
    on the exception (for example "no_person" or "invalid_video") is passed
    through to the job error; anything else becomes "engine_error".
    """

    ready: bool
    model_version: str | None

    def analyze_video(
        self,
        video_path: Path,
        *,
        on_pose: PoseCallback,
        on_prediction: PredictionCallback,
        on_progress: ProgressCallback,
        cancel_event: threading.Event,
    ) -> Mapping[str, Any]: ...

    def close(self) -> None: ...


def load_real_engine() -> Engine | None:
    """Load the production model process; report unavailable on startup failure."""

    config = {
        "model_path": os.environ.get(
            "ICARE_POSEC3D_MODEL", "models/posec3d_fall.onnx"
        ),
        "device": os.environ.get("ICARE_POSE_DEVICE", "cpu"),
        "pose_model_path": os.environ.get("ICARE_POSE_MODEL", str(ROOT / "models/yolo26n-pose.onnx")),
    }
    try:
        from icare.api.process_engine import ProcessEngine
        return ProcessEngine(config)
    except Exception:  # noqa: BLE001 - readiness must report, not crash startup
        log.exception("Engine failed to load; API will report not ready")
        return None
