"""Model loading and verification for icare_app.engine.

Everything that needs onnxruntime or rtmlib is imported inside a function, so
importing this module is side-effect free.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from icare_app.engine import EngineConfig, ModelRuntimeError, ModelUnavailableError


EXPECTED_INPUT_NAME = "pose_heatmaps"
EXPECTED_OUTPUT_NAME = "probabilities"
EXPECTED_CLASSES = ["No Fall", "Fall"]
EXPECTED_FALL_INDEX = 1
# Values the heatmap bridge (posec3d_bridge.pose_sequence_to_heatmaps) is built for.
EXPECTED_BRIDGE = {"heatmap_size": 64, "num_keypoints": 17, "sigma": 0.6, "use_keypoint_score": True}
PROBABILITY_SUM_TOLERANCE = 1e-3


def load_metadata(config: EngineConfig) -> dict[str, Any]:
    """Read posec3d_runtime.json and check it matches what the engine implements."""

    path = config.metadata_path or config.model_path.with_name("posec3d_runtime.json")
    try:
        metadata = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ModelUnavailableError(f"Model metadata not found: {path.name}") from exc
    except (OSError, ValueError) as exc:
        raise ModelUnavailableError(f"Model metadata could not be read: {path.name}") from exc

    problems: list[str] = []
    if metadata.get("classes") != EXPECTED_CLASSES:
        problems.append(f"classes {metadata.get('classes')!r} != {EXPECTED_CLASSES!r}")
    if metadata.get("fall_class_index") != EXPECTED_FALL_INDEX:
        problems.append(f"fall_class_index {metadata.get('fall_class_index')!r} != {EXPECTED_FALL_INDEX}")
    for key, expected in EXPECTED_BRIDGE.items():
        if metadata.get(key) != expected:
            problems.append(f"{key} {metadata.get(key)!r} != {expected!r}")
    for key in ("clip_len", "window_seconds", "architecture"):
        if key not in metadata:
            problems.append(f"missing {key}")
    if problems:
        raise ModelUnavailableError("Model metadata does not match the engine: " + "; ".join(problems))
    return metadata


class OnnxTemporalClassifier:
    """CPU ONNX Runtime PoseC3D with a verified two-class interface."""

    def __init__(self, session: Any, model_version: str, fall_index: int) -> None:
        self._session = session
        self.model_version = model_version
        self._fall_index = fall_index
        self._input_name = session.get_inputs()[0].name
        self._output_name = session.get_outputs()[0].name

    @classmethod
    def load(cls, model_path: Path, metadata: Mapping[str, Any]) -> "OnnxTemporalClassifier":
        model_path = Path(model_path)
        if not model_path.is_file():
            raise ModelUnavailableError(f"PoseC3D weights not found: {model_path.name}")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ModelUnavailableError("onnxruntime is not installed.") from exc

        digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
        try:
            session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        except Exception as exc:  # noqa: BLE001 - corrupt/incompatible file
            raise ModelUnavailableError(
                f"PoseC3D weights could not be loaded: {type(exc).__name__}: {exc}"
            ) from exc

        clip_len, size, joints = int(metadata["clip_len"]), int(metadata["heatmap_size"]), int(metadata["num_keypoints"])
        problems: list[str] = []
        if session.get_providers() != ["CPUExecutionProvider"]:
            problems.append(f"providers {session.get_providers()!r}")
        inputs, outputs = session.get_inputs(), session.get_outputs()
        if len(inputs) != 1 or inputs[0].name != EXPECTED_INPUT_NAME:
            problems.append(f"inputs {[i.name for i in inputs]!r}")
        elif list(inputs[0].shape[1:]) != [joints, clip_len, size, size]:
            problems.append(f"input shape {inputs[0].shape!r}")
        if len(outputs) != 1 or outputs[0].name != EXPECTED_OUTPUT_NAME:
            problems.append(f"outputs {[o.name for o in outputs]!r}")
        elif list(outputs[0].shape[1:]) != [len(EXPECTED_CLASSES)]:
            problems.append(f"output shape {outputs[0].shape!r}")
        if problems:
            raise ModelUnavailableError(
                "PoseC3D ONNX interface does not match the engine: " + "; ".join(problems)
            )

        classifier = cls(session, f"{model_path.name}@{digest[:12]}", int(metadata["fall_class_index"]))
        # Real forward pass on an empty window proves the model runs and that its
        # output really is two valid probabilities before the engine reports ready.
        try:
            classifier.predict(np.zeros((1, joints, clip_len, size, size), dtype=np.float32))
        except ModelRuntimeError as exc:
            raise ModelUnavailableError(f"PoseC3D self-check failed: {exc}") from exc
        return classifier

    def predict(self, tensor: np.ndarray) -> float:
        try:
            output = self._session.run(
                [self._output_name],
                {self._input_name: np.ascontiguousarray(tensor, dtype=np.float32)},
            )[0]
        except Exception as exc:  # noqa: BLE001
            raise ModelRuntimeError(f"ONNX Runtime failed: {type(exc).__name__}: {exc}") from exc
        probabilities = np.asarray(output, dtype=np.float64)
        if probabilities.shape != (1, len(EXPECTED_CLASSES)):
            raise ModelRuntimeError(f"Unexpected PoseC3D output shape {probabilities.shape}")
        row = probabilities[0]
        if (
            not np.isfinite(row).all()
            or row.min() < -1e-6
            or row.max() > 1.0 + 1e-6
            or not math.isclose(float(row.sum()), 1.0, abs_tol=PROBABILITY_SUM_TOLERANCE)
        ):
            raise ModelRuntimeError(f"PoseC3D output is not a probability pair: {row.tolist()}")
        return float(row[self._fall_index])

    def close(self) -> None:
        self._session = None


def load_pose_extractor(config: EngineConfig):
    """YOLOX-tiny + RTMPose-s (COCO-17). rtmlib downloads and caches the weights."""

    from icare_app.pose import RTMPoseExtractor

    try:
        return RTMPoseExtractor(device=config.device, detection_frequency=config.detection_frequency)
    except Exception as exc:  # noqa: BLE001 - missing package, no network and no cache, bad cache
        raise ModelUnavailableError(
            f"Pose models could not be loaded: {type(exc).__name__}: {exc}"
        ) from exc
