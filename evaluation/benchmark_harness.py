"""Evaluation benchmark harness for ICare inference engine (Person 4).

Measures end-to-end throughput (FPS), alert latency percentiles (median/p95),
false alarm rates per camera-hour, resource usage (CPU/RAM), and classification
accuracy in accordance with docs/interfaces/metrics.md.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore


@dataclass
class BenchmarkConfig:
    """Configuration options for benchmark evaluation runs."""
    sample_fps: float = 6.0
    model_path: Path = Path("models/posec3d_fall.onnx")
    device: str = "cpu"
    classification_threshold: float = 0.50
    repeat_runs: int = 1


@dataclass
class ClipAnnotation:
    """Ground truth annotation for a test clip."""
    clip_id: str
    filename: Path
    true_label: str  # "Fall" or "No Fall"
    fall_onset_sec: Optional[float] = None
    duration_sec: Optional[float] = None


@dataclass
class EvaluationRecord:
    """Detailed evaluation result for a single processed clip."""
    clip_id: str
    true_label: str
    predicted_label: str
    max_fall_probability: float
    fall_detected: bool
    first_alert_time_sec: Optional[float]
    alert_latency_sec: Optional[float]
    processing_time_sec: float
    total_frames_processed: int
    temporal_model_calls: int
    fps: float
    cpu_percent: float
    ram_mb: float


@dataclass
class MetricResults:
    """Aggregated evaluation metrics according to docs/interfaces/metrics.md."""
    total_clips: int = 0
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    balanced_accuracy: float = 0.0
    overall_accuracy: float = 0.0
    alert_latency_median_sec: Optional[float] = None
    alert_latency_p95_sec: Optional[float] = None
    false_alarms_per_hour: float = 0.0
    total_observed_hours: float = 0.0
    avg_fps: float = 0.0
    avg_model_calls_per_min: float = 0.0
    cpu_percent_mean: float = 0.0
    ram_mb_mean: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_percentile(data: Sequence[float], percentile: float) -> Optional[float]:
    """Calculate exact percentile (e.g. 50.0 for median, 95.0 for p95) of a float sequence."""
    if not data:
        return None
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    k = (n - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1


class BenchmarkHarness:
    """Benchmark evaluation harness for recording runtime and classification metrics."""

    def __init__(self, config: Optional[BenchmarkConfig] = None) -> None:
        self.config = config or BenchmarkConfig()

    @staticmethod
    def compute_metrics(records: Sequence[EvaluationRecord], annotations: Sequence[ClipAnnotation]) -> MetricResults:
        """Compute aggregate metrics from evaluation records."""
        results = MetricResults()
        if not records:
            return results

        results.total_clips = len(records)
        annot_map = {a.clip_id: a for a in annotations}

        latencies: List[float] = []
        total_frames = 0
        total_proc_time = 0.0
        total_model_calls = 0
        total_duration_sec = 0.0
        cpu_samples: List[float] = []
        ram_samples: List[float] = []

        for rec in records:
            annot = annot_map.get(rec.clip_id)
            is_true_fall = (rec.true_label.lower() == "fall")
            is_pred_fall = rec.fall_detected

            if is_true_fall and is_pred_fall:
                results.tp += 1
            elif not is_true_fall and is_pred_fall:
                results.fp += 1
            elif not is_true_fall and not is_pred_fall:
                results.tn += 1
            elif is_true_fall and not is_pred_fall:
                results.fn += 1

            if is_true_fall and rec.first_alert_time_sec is not None and annot and annot.fall_onset_sec is not None:
                latency = rec.first_alert_time_sec - annot.fall_onset_sec
                latencies.append(latency)

            total_frames += rec.total_frames_processed
            total_proc_time += rec.processing_time_sec
            total_model_calls += rec.temporal_model_calls
            if annot and annot.duration_sec is not None:
                total_duration_sec += annot.duration_sec

            cpu_samples.append(rec.cpu_percent)
            ram_samples.append(rec.ram_mb)

        # Classification metrics
        tp, fp, tn, fn = results.tp, results.fp, results.tn, results.fn
        results.precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        results.recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        if (results.precision + results.recall) > 0:
            results.f1_score = 2 * (results.precision * results.recall) / (results.precision + results.recall)
        else:
            results.f1_score = 0.0

        spec = (tn / (tn + fp)) if (tn + fp) > 0 else 0.0
        results.balanced_accuracy = (results.recall + spec) / 2.0
        total = tp + fp + tn + fn
        results.overall_accuracy = ((tp + tn) / total) if total > 0 else 0.0

        # Latency metrics
        if latencies:
            results.alert_latency_median_sec = calculate_percentile(latencies, 50.0)
            results.alert_latency_p95_sec = calculate_percentile(latencies, 95.0)

        # Throughput & False alarms
        if total_proc_time > 0:
            results.avg_fps = total_frames / total_proc_time
            results.avg_model_calls_per_min = (total_model_calls / total_proc_time) * 60.0

        results.total_observed_hours = total_duration_sec / 3600.0 if total_duration_sec > 0 else (total_proc_time / 3600.0)
        if results.total_observed_hours > 0:
            results.false_alarms_per_hour = results.fp / results.total_observed_hours
        else:
            results.false_alarms_per_hour = 0.0

        # Resource usage
        results.cpu_percent_mean = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
        results.ram_mb_mean = sum(ram_samples) / len(ram_samples) if ram_samples else 0.0

        return results

    def run_eval_on_predictions(
        self,
        annotations: Sequence[ClipAnnotation],
        prediction_fn: Callable[[ClipAnnotation], Tuple[List[Dict[str, Any]], float, int]]
    ) -> Tuple[List[EvaluationRecord], MetricResults]:
        """Run evaluation given a prediction function.

        prediction_fn receives a ClipAnnotation and returns:
            (predictions_list, elapsed_seconds, frame_count)
        where predictions_list contains dicts with 'timestamp_sec' and 'fall_probability'.
        """
        records: List[EvaluationRecord] = []
        for annot in annotations:
            start_cpu = psutil.cpu_percent() if psutil else 0.0
            start_mem = psutil.Process().memory_info().rss / (1024 * 1024) if psutil else 0.0

            preds, elapsed, num_frames = prediction_fn(annot)

            end_cpu = psutil.cpu_percent() if psutil else 0.0
            end_mem = psutil.Process().memory_info().rss / (1024 * 1024) if psutil else 0.0

            max_prob = max((p.get("fall_probability", 0.0) for p in preds), default=0.0)
            alert_time: Optional[float] = None
            for p in preds:
                if p.get("fall_probability", 0.0) >= self.config.classification_threshold:
                    alert_time = p.get("timestamp_sec")
                    break

            fall_detected = (max_prob >= self.config.classification_threshold)
            pred_label = "Fall" if fall_detected else "No Fall"

            lat_sec: Optional[float] = None
            if fall_detected and alert_time is not None and annot.fall_onset_sec is not None:
                lat_sec = alert_time - annot.fall_onset_sec

            fps = (num_frames / elapsed) if elapsed > 0 else 0.0

            record = EvaluationRecord(
                clip_id=annot.clip_id,
                true_label=annot.true_label,
                predicted_label=pred_label,
                max_fall_probability=max_prob,
                fall_detected=fall_detected,
                first_alert_time_sec=alert_time,
                alert_latency_sec=lat_sec,
                processing_time_sec=elapsed,
                total_frames_processed=num_frames,
                temporal_model_calls=len(preds),
                fps=fps,
                cpu_percent=max(start_cpu, end_cpu),
                ram_mb=max(start_mem, end_mem),
            )
            records.append(record)

        metrics = self.compute_metrics(records, annotations)
        return records, metrics
