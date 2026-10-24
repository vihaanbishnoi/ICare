"""Daily summary report generation from local dummy logs using Ollama's llama3.2:1b."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2:1b"

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV_PATH = Path(__file__).resolve().parent / "data" / "daily_logs.csv"


def get_csv_path() -> Path:
    """Locate the daily logs CSV file."""
    env_path = os.environ.get("ICARE_DAILY_LOGS_CSV")
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    if DEFAULT_CSV_PATH.is_file():
        return DEFAULT_CSV_PATH
    fallback = ROOT / "data" / "daily_logs.csv"
    if fallback.is_file():
        return fallback
    return DEFAULT_CSV_PATH


def load_daily_logs(csv_path: Path | None = None) -> list[dict[str, Any]]:
    """Read logs from the local CSV file."""
    path = csv_path or get_csv_path()
    if not path.is_file():
        log.warning("Daily logs CSV file not found at %s", path)
        return []

    logs: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            logs.append({
                "log_id": row.get("log_id", ""),
                "timestamp": row.get("timestamp", ""),
                "resident_id": row.get("resident_id", ""),
                "resident_name": row.get("resident_name", ""),
                "room": row.get("room", ""),
                "wing": row.get("wing", ""),
                "event_type": row.get("event_type", ""),
                "confidence": float(row["confidence"]) if row.get("confidence") else 0.0,
                "status": row.get("status", ""),
                "response_time_seconds": int(row["response_time_seconds"]) if row.get("response_time_seconds") else None,
                "attended_by": row.get("attended_by", ""),
                "staff_notes": row.get("staff_notes", ""),
            })
    return logs


def format_logs_for_prompt(logs: list[dict[str, Any]]) -> str:
    """Format logs into a structured markdown table for LLM consumption."""
    lines = [
        "| Time | Resident | Room | Wing | Event | Confidence | Response | Attended By | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    ]
    for r in logs:
        time_str = r.get("timestamp", "").split()[-1] if " " in r.get("timestamp", "") else r.get("timestamp", "")
        conf_pct = f"{int(r.get('confidence', 0) * 100)}%"
        resp = f"{r.get('response_time_seconds')}s" if r.get("response_time_seconds") is not None else "-"
        lines.append(
            f"| {time_str} | {r.get('resident_name')} | {r.get('room')} | {r.get('wing')} | "
            f"{r.get('event_type')} | {conf_pct} | {resp} | {r.get('attended_by')} | {r.get('staff_notes')} |"
        )
    return "\n".join(lines)


def build_summary_prompt(logs: list[dict[str, Any]]) -> str:
    """Construct prompt for Ollama llama3.2:1b."""
    table = format_logs_for_prompt(logs)
    return (
        "You are an expert clinical care assistant at an elderly care facility using the ICare fall-monitoring system.\n"
        "Analyze the following incident and activity logs recorded today across the facility:\n\n"
        f"{table}\n\n"
        "Generate a structured, professional Daily Fall Monitoring Summary Report with these 3 sections:\n"
        "1. Executive Summary: Key metrics (total falls, average response time, peak danger wings/rooms).\n"
        "2. Clinical & Incident Analysis: Key residents affected (specifically repeat fallers or injuries), staff response times, and care interventions.\n"
        "3. Shift Handoff Recommendations: Actionable care plan adjustments and high-risk residents to monitor closely during the next shift.\n\n"
        "Keep the summary clear, professional, and directly grounded in the provided logs."
    )


def rule_based_fallback_summary(logs: list[dict[str, Any]]) -> str:
    """Deterministic fallback summary when Ollama is unreachable."""
    if not logs:
        return "No daily logs recorded for summary generation."

    total_logs = len(logs)
    falls = [l for l in logs if "Fall Detected" in l.get("event_type", "")]
    total_falls = len(falls)
    response_times = [l["response_time_seconds"] for l in logs if l.get("response_time_seconds") is not None]
    avg_resp = (sum(response_times) / len(response_times)) if response_times else 0

    rooms_with_falls = [f.get("room") for f in falls if f.get("room")]
    residents_with_falls = [f.get("resident_name") for f in falls if f.get("resident_name")]
    repeat_fallers = [name for name in set(residents_with_falls) if residents_with_falls.count(name) > 1]

    lines = [
        "### Daily Fall Monitoring Summary Report (Rule-based Fallback)",
        "",
        "**1. Executive Summary**",
        f"- **Total Monitoring Events:** {total_logs}",
        f"- **Confirmed Falls:** {total_falls}",
        f"- **Average Staff Response Time:** {avg_resp:.1f} seconds",
        f"- **High-Risk Rooms:** {', '.join(set(rooms_with_falls)) if rooms_with_falls else 'None'}",
        "",
        "**2. Clinical & Incident Analysis**",
    ]
    if falls:
        for f in falls:
            lines.append(
                f"- **{f.get('resident_name')} (Room {f.get('room')}, {f.get('wing')} Wing):** "
                f"{f.get('event_type')} (Confidence: {int(f.get('confidence', 0)*100)}%). "
                f"Response: {f.get('response_time_seconds')}s by {f.get('attended_by')}. Note: {f.get('staff_notes')}"
            )
    else:
        lines.append("- No fall incidents were recorded today.")

    lines.extend([
        "",
        "**3. Shift Handoff Recommendations**",
    ])
    if repeat_fallers:
        lines.append(f"- **High Alert:** {', '.join(repeat_fallers)} experienced multiple fall events. Schedule mobility review and sensor bed-pad check.")
    lines.append("- Maintain active monitoring on the West and East wings; verify all grab bars and unassisted transfer aids.")

    return "\n".join(lines)


def summarize_daily_logs(
    logs: list[dict[str, Any]] | None = None,
    model: str = DEFAULT_MODEL,
    ollama_host: str | None = None,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    """Execute LLM summarization via Ollama with fallback."""
    if logs is None:
        logs = load_daily_logs()

    host = (ollama_host or os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST).rstrip("/")
    endpoint = f"{host}/api/generate"
    now_iso = datetime.now(timezone.utc).isoformat()

    if not logs:
        return {
            "status": "empty",
            "model": model,
            "summary": "No logs available to summarise.",
            "log_count": 0,
            "generated_at_utc": now_iso,
            "ollama_connected": False,
        }

    prompt = build_summary_prompt(logs)
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            summary_text = data.get("response", "").strip()
            return {
                "status": "success",
                "model": model,
                "summary": summary_text,
                "log_count": len(logs),
                "generated_at_utc": now_iso,
                "ollama_connected": True,
            }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("Ollama request to %s failed (%s). Using fallback summary.", endpoint, exc)
        fallback = rule_based_fallback_summary(logs)
        return {
            "status": "fallback",
            "model": model,
            "summary": fallback,
            "log_count": len(logs),
            "generated_at_utc": now_iso,
            "ollama_connected": False,
            "notice": f"Ollama connection unavailable ({exc}). Displaying analyzed summary.",
        }
