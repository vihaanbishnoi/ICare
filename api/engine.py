"""Engine boundary injected into the job worker.

The real engine is Person 1's icare_app.engine (docs/interfaces/inference.md).
The API never imports pose/ONNX code directly, and it never substitutes a fake
engine: when no real engine loads, /ready and job creation return 503.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
import threading
from typing import Any, Callable, Mapping, Protocol


log = logging.getLogger(__name__)

PoseCallback = Callable[[Mapping[str, Any]], None]
PredictionCallback = Callable[[Mapping[str, Any]], None]
ProgressCallback = Callable[[float | None], None]


class Engine(Protocol):
    """What the API expects from load_engine(config).

    analyze_video calls on_pose/on_prediction with records using the field names
    in docs/interfaces/inference.md, and returns a summary only after the final
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
    """Load Person 1's engine if it exists; return None instead of faking it."""

    try:
        from icare_app.engine import load_engine  # type: ignore[import-not-found]
    except ImportError:
        log.warning("icare_app.engine is not available; API will report not ready")
        return None
    config = {
        "model_path": os.environ.get(
            "ICARE_POSEC3D_MODEL", "models/posec3d_fall.onnx"
        ),
        "device": os.environ.get("ICARE_POSE_DEVICE", "cpu"),
    }
    try:
        return load_engine(config)
    except Exception:  # noqa: BLE001 - readiness must report, not crash startup
        log.exception("Engine failed to load; API will report not ready")
        return None
