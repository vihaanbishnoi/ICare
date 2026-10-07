from __future__ import annotations

import csv
import json
from pathlib import Path


REPORT_ROOT = Path("artifacts/reports")
EVENT_FIELDS = [
    "event_id",
    "detected_at_seconds",
    "confidence",
    "source",
    "created_at_utc",
    "fall_onset_seconds",
    "alert_latency_seconds",
]
INFERENCE_FIELDS = [
    "timestamp_seconds",
    "fall_probability",
    "inference_ms",
    "window_start_seconds",
    "source_pose_count",
    "urgency",
    "reliability",
    "process_cpu_percent",
    "process_rss_mb",
]


def write_report(snapshot: dict, report_stem: str) -> tuple[str, str]:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    safe_stem = "".join(
        character
        for character in report_stem
        if character.isalnum() or character in "-_"
    )
    json_path = REPORT_ROOT / f"{safe_stem}.json"
    csv_path = REPORT_ROOT / f"{safe_stem}.csv"
    inference_csv_path = REPORT_ROOT / f"{safe_stem}_inference.csv"

    report_snapshot = dict(snapshot)
    report_snapshot["inference_log_csv"] = str(inference_csv_path.resolve())
    json_path.write_text(json.dumps(report_snapshot, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=EVENT_FIELDS)
        writer.writeheader()
        writer.writerows(snapshot.get("events", []))

    with inference_csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=INFERENCE_FIELDS)
        writer.writeheader()
        writer.writerows(snapshot.get("inference_records", []))

    return str(json_path.resolve()), str(csv_path.resolve())


def event_rows(snapshot: dict) -> list[list]:
    rows = []
    for event in snapshot.get("events", []):
        rows.append(
            [
                event["event_id"],
                _clock(event["detected_at_seconds"]),
                f"{event['confidence']:.1%}",
            ]
        )
    return rows


def _clock(seconds: float) -> str:
    minutes, remaining = divmod(float(seconds), 60)
    return f"{int(minutes):02d}:{remaining:04.1f}"
