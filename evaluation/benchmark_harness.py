"""Evaluation benchmark harness for ICare inference engine (Person 4).

Measures throughput (FPS), alert latency percentiles (median/p95), false alarm rates
per camera-hour, resource usage (CPU/RAM), and classification metrics in accordance
with docs/interfaces/metrics.md and icare_app.engine contracts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from api.incidents import IncidentTracker


@dataclass
class BenchmarkConfig:
    """Configuration options for benchmark evaluation runs."""
    sample_fps: float = 6.0
    model_path: Path = Path("models/posec3d_fall.onnx")
    device: str = "cpu"
    repeat_runs: int = 1


@dataclass
class ClipAnnotation:
    """Ground truth annotation for an evaluated video clip."""
    clip_id: str
    filename: Path
    true_label: str  # "Fall" or "No Fall"
    fall_onset_seconds: Optional[float] = None
    duration_seconds: Optional[float] = None
    provenance_status: str = "pending"


@dataclass
class EvaluationRecord:
    """Evaluation result for a single processed clip."""
    clip_id: str
    true_label: str
    predicted_label: str
    max_fall_probability: float
    incidents_detected: int
    first_incident_timestamp_seconds: Optional[float]
    alert_latency_seconds: Optional[float]
    processing_time_seconds: float
    total_frames_processed: int
    temporal_model_calls: int
    fps: Optional[float]
    mean_pose_inference_ms: Optional[float]
    cpu_percent_mean: Optional[float]
    ram_mb_peak: Optional[float]


@dataclass
class MetricResults:
    """Aggregated evaluation metrics according to docs/interfaces/metrics.md.

    Unmeasured values stay None (never zero or fabricated numbers).
    """
    total_clips: int = 0
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    balanced_accuracy: Optional[float] = None
    overall_accuracy: Optional[float] = None
    alert_latency_median_seconds: Optional[float] = None
    alert_latency_p95_seconds: Optional[float] = None
    false_alarms_per_hour: Optional[float] = None
    total_observed_hours: Optional[float] = None
    avg_fps: Optional[float] = None
    avg_model_calls_per_min: Optional[float] = None
    cpu_percent_mean: Optional[float] = None
    ram_mb_peak_mean: Optional[float] = None

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
    """Benchmark evaluation harness for analyzing inference engine outputs."""

    def __init__(self, config: Optional[BenchmarkConfig] = None) -> None:
        self.config = config or BenchmarkConfig()

    @staticmethod
    def compute_metrics(records: Sequence[EvaluationRecord], annotations: Sequence[ClipAnnotation]) -> MetricResults:
        """Compute aggregate metrics from evaluation records.
        
        Unmeasured fields remain None per docs/interfaces/metrics.md.
        """
        results = MetricResults()
        if not records:
            return results

        results.total_clips = len(records)
        annot_map = {a.clip_id: a for a in annotations}

        latencies: List[float] = []
        total_frames = 0
        total_proc_time = 0.0
        total_model_calls = 0
        observed_seconds_list: List[float] = []
        total_false_incidents = 0

        cpu_samples: List[float] = []
        ram_samples: List[float] = []

        for rec in records:
            annot = annot_map.get(rec.clip_id)
            is_true_fall = (rec.true_label.lower() == "fall")
            is_pred_fall = (rec.incidents_detected > 0 or rec.predicted_label.lower() == "fall")

            if is_true_fall and is_pred_fall:
                results.tp += 1
            elif not is_true_fall and is_pred_fall:
                results.fp += 1
                total_false_incidents += rec.incidents_detected
            elif not is_true_fall and not is_pred_fall:
                results.tn += 1
            elif is_true_fall and not is_pred_fall:
                results.fn += 1

            if is_true_fall and rec.alert_latency_seconds is not None:
                latencies.append(rec.alert_latency_seconds)

            total_frames += rec.total_frames_processed
            total_proc_time += rec.processing_time_seconds
            total_model_calls += rec.temporal_model_calls

            if annot and annot.duration_seconds is not None and annot.duration_seconds > 0:
                observed_seconds_list.append(annot.duration_seconds)

            if rec.cpu_percent_mean is not None:
                cpu_samples.append(rec.cpu_percent_mean)
            if rec.ram_mb_peak is not None:
                ram_samples.append(rec.ram_mb_peak)

        # Classification metrics
        tp, fp, tn, fn = results.tp, results.fp, results.tn, results.fn
        total = tp + fp + tn + fn

        if total > 0:
            results.overall_accuracy = (tp + tn) / total
            results.precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
            results.recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
            if (results.precision is not None and results.recall is not None and (results.precision + results.recall) > 0):
                results.f1_score = 2 * (results.precision * results.recall) / (results.precision + results.recall)
            else:
                results.f1_score = 0.0
            spec = (tn / (tn + fp)) if (tn + fp) > 0 else 0.0
            results.balanced_accuracy = (results.recall + spec) / 2.0

        # Latency metrics
        if latencies:
            results.alert_latency_median_seconds = calculate_percentile(latencies, 50.0)
            results.alert_latency_p95_seconds = calculate_percentile(latencies, 95.0)

        # Throughput & False Alarm Rate
        if total_proc_time > 0:
            results.avg_fps = total_frames / total_proc_time
            results.avg_model_calls_per_min = (total_model_calls / total_proc_time) * 60.0

        # Observed hours: strictly based on annotated clip duration (never wall clock fallback)
        if observed_seconds_list:
            total_obs_sec = sum(observed_seconds_list)
            results.total_observed_hours = total_obs_sec / 3600.0
            if results.total_observed_hours > 0:
                results.false_alarms_per_hour = total_false_incidents / results.total_observed_hours

        # Resource usage: stay None if unmeasured
        if cpu_samples:
            results.cpu_percent_mean = sum(cpu_samples) / len(cpu_samples)
        if ram_samples:
            results.ram_mb_peak_mean = sum(ram_samples) / len(ram_samples)

        return results

    def run_engine_clip(self, engine: Any, annotation: ClipAnnotation) -> EvaluationRecord:
        """Run real inference engine on one clip using icare_app.engine interface."""
        poses: List[Dict[str, Any]] = []
        predictions: List[Dict[str, Any]] = []
        tracker = IncidentTracker()
        incidents = 0
        first_incident_ts: Optional[float] = None

        def on_prediction(pred: Dict[str, Any]) -> None:
            nonlocal incidents, first_incident_ts
            predictions.append(pred)
            prob = pred.get("fall_probability", 0.0)
            if tracker.observe(prob):
                incidents += 1
                if first_incident_ts is None:
                    first_incident_ts = pred.get("timestamp_seconds")

        start_time = time.perf_counter()
        error_code: Optional[str] = None
        try:
            summary = engine.analyze_video(
                annotation.filename,
                on_pose=poses.append,
                on_prediction=on_prediction,
                on_progress=lambda p: None,
                cancel_event=threading.Event(),
            )
            elapsed = time.perf_counter() - start_time
            metrics = summary.get("metrics", {})
        except Exception as exc:
            elapsed = time.perf_counter() - start_time
            error_code = getattr(exc, "code", type(exc).__name__)
            summary = {}
            metrics = {}

        max_prob = max((p.get("fall_probability", 0.0) for p in predictions), default=0.0)
        if error_code is not None:
            pred_label = f"Failed ({error_code})"
        else:
            pred_label = "fall" if incidents > 0 else "no_fall"

        lat_sec: Optional[float] = None
        if incidents > 0 and first_incident_ts is not None and annotation.fall_onset_seconds is not None:
            lat_sec = first_incident_ts - annotation.fall_onset_seconds

        fps = metrics.get("processed_frames_per_second")
        frames_proc = metrics.get("sampled_frames", len(poses))

        return EvaluationRecord(
            clip_id=annotation.clip_id,
            true_label=annotation.true_label,
            predicted_label=pred_label,
            max_fall_probability=max_prob,
            incidents_detected=incidents,
            first_incident_timestamp_seconds=first_incident_ts,
            alert_latency_seconds=lat_sec,
            processing_time_seconds=elapsed,
            total_frames_processed=frames_proc,
            temporal_model_calls=len(predictions),
            fps=fps,
            mean_pose_inference_ms=metrics.get("mean_pose_inference_ms"),
            cpu_percent_mean=metrics.get("process_cpu_percent_mean"),
            ram_mb_peak=metrics.get("process_rss_mb_peak"),
        )
