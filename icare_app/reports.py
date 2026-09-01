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
    json_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=EVENT_FIELDS)
        writer.writeheader()
        writer.writerows(snapshot.get("events", []))

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
