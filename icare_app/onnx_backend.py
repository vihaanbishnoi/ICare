from __future__ import annotations

from pathlib import Path
from threading import Lock

import numpy as np

from icare_app.inference import ModelOutput
from icare_app.pose import PoseFrame, PosePreviewBackend


class PoseC3DONNXBackend(PosePreviewBackend):
    """RTMPose plus rolling PoseC3D ONNX inference."""

    available = True

    def __init__(
        self,
        model_path: str | Path,
        device: str = "cpu",
        inference_width: int = 416,
        prediction_interval_seconds: float = 0.75,
    ) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("Install onnxruntime before loading PoseC3D.") from exc

        self.model_path = Path(model_path).resolve()
        if not self.model_path.exists():
            raise FileNotFoundError(self.model_path)
        self.name = f"RTMPose + PoseC3D ({self.model_path.name})"
        self.prediction_interval_seconds = float(prediction_interval_seconds)
        self._prediction_lock = Lock()
        self._pending_output: ModelOutput | None = None
        self._last_prediction_seconds = float("-inf")
        self.session = ort.InferenceSession(
            str(self.model_path), providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        output_shape = self.session.get_outputs()[0].shape
        if output_shape[-1] != 2:
            raise ValueError(f"Expected two PoseC3D classes, received {output_shape}")
        super().__init__(device=device, inference_width=inference_width)

    def reset(self) -> None:
        super().reset()
        with self._prediction_lock:
            self._pending_output = None
            self._last_prediction_seconds = float("-inf")

    def process_frame(self, frame_rgb: np.ndarray, timestamp_seconds: float):
        super().process_frame(frame_rgb, timestamp_seconds)
        with self._prediction_lock:
            output = self._pending_output
            self._pending_output = None
        return output

    def on_pose_ready(self, pose: PoseFrame) -> None:
        if (
            pose.timestamp_seconds - self._last_prediction_seconds
            < self.prediction_interval_seconds
        ):
            return
        model_input = self.sequence_buffer.build()
        if model_input is None:
            return
        probabilities = self.session.run(
            None, {self.input_name: model_input.tensor.astype(np.float32, copy=False)}
        )[0]
        fall_probability = float(np.asarray(probabilities)[0, 1])
        with self._prediction_lock:
            self._pending_output = ModelOutput(
                timestamp_seconds=model_input.end_seconds,
                fall_probability=fall_probability,
            )
            self._last_prediction_seconds = model_input.end_seconds
