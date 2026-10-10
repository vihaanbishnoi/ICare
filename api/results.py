"""Builds the Result document and its owned json/csv reports for one job."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping

from api.schemas import Result


PREFIX = "/api/v1"
CSV_FIELDS = [
    "timestamp_seconds",
    "fall_probability",
    "window_start_seconds",
    "source_pose_count",
    "inference_ms",
    "urgency",
    "reliability",
    "incident_id",
]


def job_url(job_id: str, suffix: str = "") -> str:
    return f"{PREFIX}/jobs/{job_id}{suffix}"


def build_result(
    job_id: str,
    summary: Mapping[str, Any],
    model_version: str | None,
    predictions: list[dict[str, Any]],
    poses: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    processing_seconds: float,
) -> dict[str, Any]:
    inference_times = [
        p["inference_ms"] for p in predictions if p.get("inference_ms") is not None
    ]
    metrics: dict[str, Any] = {
        "posec3d_calls": len(predictions),
        "pose_count": len(poses),
        "mean_inference_ms": mean(inference_times) if inference_times else None,
        "median_inference_ms": median(inference_times) if inference_times else None,
        "processing_seconds": round(processing_seconds, 3),
    }
    # Engine-measured values (CPU/RAM samples etc.) pass through; never invented.
    for name, value in dict(summary.get("metrics") or {}).items():
        if value is None or isinstance(value, (int, float)):
            metrics.setdefault(name, value)
    document = {
        "job_id": job_id,
        "duration_seconds": float(summary["duration_seconds"]),
        "frame_width": int(summary["frame_width"]),
        "frame_height": int(summary["frame_height"]),
        "model_version": model_version,
        "analysis_mode": "on_demand",
        "media_url": job_url(job_id, "/media"),
        "predictions": predictions,
        "poses": poses,
        "incidents": incidents,
        "metrics": metrics,
        "reports": {
            "json": job_url(job_id, "/reports/json"),
            "csv": job_url(job_id, "/reports/csv"),
        },
    }
    # Reject non-finite summary/metric values before a job is marked complete.
    return Result.model_validate(document).model_dump()


class ResultTooLarge(ValueError):
    pass


def write_outputs(job_dir: Path, result: dict[str, Any], max_bytes: int = 5 * 1024 * 1024) -> None:
    """Write result.json, report.json and report.csv inside the job folder."""

    result_json = json.dumps(result, allow_nan=False)
    report_json = json.dumps(result, indent=2, allow_nan=False)
    incident_at = {i["detected_at_seconds"]: i["incident_id"] for i in result["incidents"]}
    with io.StringIO(newline='') as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for prediction in result["predictions"]:
            row = dict(prediction)
            row["incident_id"] = incident_at.get(prediction["timestamp_seconds"], "")
            writer.writerow(row)
        report_csv = file.getvalue()
    if sum(len(value.encode('utf-8')) for value in (result_json, report_json, report_csv)) > max_bytes:
        raise ResultTooLarge('Result documents exceed the reserved storage budget.')
    for filename, content in [('result.json', result_json), ('report.json', report_json), ('report.csv', report_csv)]:
        (job_dir / filename).write_text(content, encoding='utf-8', newline='')
