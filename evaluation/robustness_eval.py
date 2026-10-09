"""Robustness and perturbation evaluation framework for ICare (Person 4).

Evaluates pose pipeline degradation under synthetic noise, missing keypoint joints,
frame cropping/occlusions, and hard negative cases.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from evaluation.benchmark_harness import BenchmarkHarness, ClipAnnotation, EvaluationRecord, MetricResults


@dataclass
class RobustnessLevelResult:
    """Evaluation metrics at a specific perturbation intensity level."""
    perturbation_type: str
    intensity: float
    metrics: MetricResults
    records: List[EvaluationRecord]


def apply_keypoint_dropout(
    keypoints: List[List[float]],
    dropout_prob: float = 0.1,
    seed: Optional[int] = None
) -> List[List[float]]:
    """Randomly zero out keypoint coordinates and confidence scores with probability dropout_prob.
    
    Each keypoint in keypoints is expected to be [x, y, score] or [x, y].
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
    keypoints: List[List[float]],
    noise_std: float = 2.0,
    seed: Optional[int] = None
) -> List[List[float]]:
    """Add Gaussian noise to keypoint x and y coordinates.
    
    Keypoints: list of [x, y] or [x, y, score].
    """
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
    keypoints: List[List[float]],
    crop_ratio: float = 0.2,
    img_width: float = 416.0,
    img_height: float = 416.0
) -> List[List[float]]:
    """Simulate frame edge cropping by setting keypoints falling outside the cropped area to 0.0.
    
    crop_ratio: fraction of frame border cropped out from top/left/right/bottom.
    """
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
    """Evaluates detector robustness across varying perturbation types and levels."""

    def __init__(self, harness: Optional[BenchmarkHarness] = None) -> None:
        self.harness = harness or BenchmarkHarness()

    def evaluate_perturbation_range(
        self,
        annotations: Sequence[ClipAnnotation],
        perturbation_type: str,
        intensities: Sequence[float],
        predictor_factory: Callable[[str, float], Callable[[ClipAnnotation], Tuple[List[Dict[str, Any]], float, int]]]
    ) -> List[RobustnessLevelResult]:
        """Evaluate performance across a sequence of perturbation intensity levels.
        
        predictor_factory receives (perturbation_type, intensity) and returns a prediction_fn.
        """
        results: List[RobustnessLevelResult] = []
        for level in intensities:
            prediction_fn = predictor_factory(perturbation_type, level)
            records, metrics = self.harness.run_eval_on_predictions(annotations, prediction_fn)
            results.append(RobustnessLevelResult(
                perturbation_type=perturbation_type,
                intensity=level,
                metrics=metrics,
                records=records,
            ))
        return results
