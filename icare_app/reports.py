from __future__ import annotations

import csv
import json
from pathlib import Path


REPORT_ROOT = Path("artifacts/reports")


def write_report(snapshot: dict, report_stem: str) -> tuple[str, str]:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    safe_stem = "".join(character for character in report_stem if character.isalnum() or character in "-_")
    json_path = REPORT_ROOT / f"{safe_stem}.json"
    csv_path = REPORT_ROOT / f"{safe_stem}.csv"

    json_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    fields = [
        "event_id",
        "timestamp_seconds",
        "confidence",
        "activity_id",
        "activity_name",
        "source",
        "created_at_utc",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(snapshot.get("events", []))

    return str(json_path.resolve()), str(csv_path.resolve())


def event_rows(snapshot: dict) -> list[list]:
    return [
        [
            event["event_id"],
            event["timestamp_seconds"],
            event["confidence"],
            event["activity_name"],
            event["source"],
        ]
        for event in snapshot.get("events", [])
    ]

