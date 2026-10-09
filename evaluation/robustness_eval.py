"""Robustness and perturbation evaluation framework for ICare (Person 4).

Evaluates pose pipeline degradation under synthetic noise, missing keypoint joints,
frame cropping/occlusions, and hard negative activity cases (sitting fast, lying down,
crouching, picking up an object, tying a shoe, leaving the frame).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from evaluation.benchmark_harness import BenchmarkHarness, ClipAnnotation, EvaluationRecord, MetricResults


HARD_NEGATIVE_ACTIVITIES = [
    {"activity_id": "fast_sitting", "title": "Fast sitting in chair", "expected_outcome": "No Fall"},
    {"activity_id": "lying_down", "title": "Normal lying down on bed/sofa", "expected_outcome": "No Fall"},
    {"activity_id": "crouching", "title": "Crouching to pick up object", "expected_outcome": "No Fall"},
    {"activity_id": "tying_shoe", "title": "Bending down tying shoe", "expected_outcome": "No Fall"},
    {"activity_id": "leaving_frame", "title": "Rapidly leaving camera view", "expected_outcome": "No Fall"},
    {"activity_id": "camera_occlusion", "title": "Partial camera occlusion", "expected_outcome": "No Fall"},
]


@dataclass
class RobustnessLevelResult:
    """Evaluation metrics at a specific perturbation intensity level."""
    perturbation_type: str
    intensity: float
    metrics: MetricResults
    records: List[EvaluationRecord]


def apply_keypoint_dropout(
    keypoints: Sequence[Sequence[float]],
    dropout_prob: float = 0.1,
    seed: Optional[int] = None
) -> List[List[float]]:
    """Randomly zero out keypoint coordinates and confidence scores with probability dropout_prob.
    
    Each keypoint is expected to be [x, y, score] or [x, y].
    """
    if dropout_prob <= 0.0:
        return [list(kp) for kp in keypoints]
    
    rng = random.Random(seed) if seed is not None else random
    perturbed: List[List[float]] = []
    for kp in keypoints:
        if rng.random() < dropout_prob:
            perturbed.append([0.0] * len(kp))
        else:
            perturbed.append(list(kp))
    return perturbed


def apply_keypoint_noise(
    keypoints: Sequence[Sequence[float]],
    noise_std: float = 2.0,
    seed: Optional[int] = None
) -> List[List[float]]:
    """Add Gaussian noise to keypoint x and y coordinates."""
    if noise_std <= 0.0:
        return [list(kp) for kp in keypoints]

    rng = random.Random(seed) if seed is not None else random
    perturbed: List[List[float]] = []
    for kp in keypoints:
        new_kp = list(kp)
        if len(new_kp) >= 2 and (new_kp[0] != 0.0 or new_kp[1] != 0.0):
            new_kp[0] += rng.gauss(0.0, noise_std)
            new_kp[1] += rng.gauss(0.0, noise_std)
        perturbed.append(new_kp)
    return perturbed


def apply_frame_cropping(
    keypoints: Sequence[Sequence[float]],
    crop_ratio: float = 0.2,
    img_width: float = 416.0,
    img_height: float = 416.0
) -> List[List[float]]:
    """Simulate frame edge cropping by setting keypoints falling outside the cropped area to 0.0."""
    if crop_ratio <= 0.0:
        return [list(kp) for kp in keypoints]

    min_x = img_width * crop_ratio
    max_x = img_width * (1.0 - crop_ratio)
    min_y = img_height * crop_ratio
    max_y = img_height * (1.0 - crop_ratio)

    perturbed: List[List[float]] = []
    for kp in keypoints:
        new_kp = list(kp)
        if len(new_kp) >= 2:
            x, y = new_kp[0], new_kp[1]
            if x < min_x or x > max_x or y < min_y or y > max_y:
                new_kp = [0.0] * len(kp)
        perturbed.append(new_kp)
    return perturbed


class RobustnessEvaluator:
    """Evaluates detector robustness across varying perturbation types and hard-negative cases."""

    def __init__(self, harness: Optional[BenchmarkHarness] = None) -> None:
        self.harness = harness or BenchmarkHarness()

    def evaluate_hard_negatives(
        self,
        engine: Any,
        hard_negative_annotations: Sequence[ClipAnnotation]
    ) -> MetricResults:
        """Run evaluation exclusively on hard-negative non-fall activity clips."""
        records: List[EvaluationRecord] = []
        for annot in hard_negative_annotations:
            if annot.filename.is_file():
                rec = self.harness.run_engine_clip(engine, annot)
                records.append(rec)
        return self.harness.compute_metrics(records, hard_negative_annotations)

    def evaluate_perturbation_range(
        self,
        records_fn: Callable[[str, float], List[EvaluationRecord]],
        annotations: Sequence[ClipAnnotation],
        perturbation_type: str,
        intensities: Sequence[float]
    ) -> List[RobustnessLevelResult]:
        """Evaluate performance degradation across perturbation intensity levels."""
        results: List[RobustnessLevelResult] = []
        for level in intensities:
            records = records_fn(perturbation_type, level)
            metrics = self.harness.compute_metrics(records, annotations)
            results.append(RobustnessLevelResult(
                perturbation_type=perturbation_type,
                intensity=level,
                metrics=metrics,
                records=records,
            ))
        return results
