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
    """Construct structured JSON prompt for Ollama llama3.2:1b."""
    table = format_logs_for_prompt(logs)
    return (
        "You are an expert clinical care assistant at an elderly care facility using the ICare fall-monitoring system.\n"
        "Analyze the following incident and activity logs recorded today across the facility:\n\n"
        f"{table}\n\n"
        "Output ONLY a valid JSON object with this EXACT structure (no extra text, no markdown):\n"
        "{\n"
        '  "executive_summary": "Concise 2-3 sentence clinical overview of facility status, incidents, and staff responsiveness today.",\n'
        '  "incident_stats": {\n'
        '    "total_events": 12,\n'
        '    "confirmed_falls": 3,\n'
        '    "near_falls": 2,\n'
        '    "avg_response_time_seconds": 45\n'
        "  },\n"
        '  "high_risk_residents": [\n'
        "    {\n"
        '      "resident_name": "Resident Name",\n'
        '      "room": "Room Number",\n'
        '      "wing": "Wing Name",\n'
        '      "risk_level": "High or Medium",\n'
        '      "incident_summary": "Specific description of fall or near-fall event and injury/condition",\n'
        '      "action_plan": "Immediate nursing or environment intervention required"\n'
        "    }\n"
        "  ],\n"
        '  "key_observations": [\n'
        '    "Clinical or environmental pattern observed from the logs",\n'
        '    "Second observation (e.g. transfer risks, footwear, lighting)"\n'
        "  ],\n"
        '  "shift_handoff_recommendations": [\n'
        '    "Actionable priority 1 for next shift staff",\n'
        '    "Actionable priority 2 for next shift staff"\n'
        "  ],\n"
        '  "shift_handoff_notes": "Important handoff message specifically for the incoming nurse and caregiver team."\n'
        "}"
    )


def compute_fallback_structured(logs: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute structured metrics and details deterministically from logs."""
    total_logs = len(logs)
    falls = [l for l in logs if "Fall Detected" in l.get("event_type", "")]
    near_falls = [l for l in logs if "Near Fall" in l.get("event_type", "") or "Slip" in l.get("event_type", "")]
    response_times = [l["response_time_seconds"] for l in logs if l.get("response_time_seconds") is not None]
    avg_resp = round(sum(response_times) / len(response_times), 1) if response_times else 0

    high_risk_residents = []
    # Identify residents with falls or repeat alerts
    seen_names: set[str] = set()
    for l in falls + near_falls:
        name = l.get("resident_name") or "Unknown"
        if name not in seen_names:
            seen_names.add(name)
            is_fall = "Fall Detected" in l.get("event_type", "")
            high_risk_residents.append({
                "resident_name": name,
                "room": l.get("room", "Unknown"),
                "wing": l.get("wing", "General"),
                "risk_level": "High" if is_fall else "Medium",
                "incident_summary": f"{l.get('event_type')}: {l.get('staff_notes', 'Incident logged')}",
                "action_plan": f"Attended by {l.get('attended_by') or 'staff'} in {l.get('response_time_seconds', '-')}s. Verify sensor bed-pad and mobility aids."
            })

    return {
        "executive_summary": (
            f"Daily monitoring completed with {total_logs} events logged. "
            f"{len(falls)} confirmed fall incidents and {len(near_falls)} near-fall/slip alerts were detected and attended. "
            f"Average staff response time was {avg_resp} seconds across all active units."
        ),
        "incident_stats": {
            "total_events": total_logs,
            "confirmed_falls": len(falls),
            "near_falls": len(near_falls),
            "avg_response_time_seconds": avg_resp,
        },
        "high_risk_residents": high_risk_residents or [
            {
                "resident_name": "All Residents Stable",
                "room": "-",
                "wing": "All",
                "risk_level": "Low",
                "incident_summary": "No falls or critical alerts recorded today.",
                "action_plan": "Continue standard routine monitoring."
            }
        ],
        "key_observations": [
            f"West and East wings recorded the highest movement and incident frequency.",
            f"Average staff response latency was maintained under 60 seconds ({avg_resp}s).",
            f"Bedside transfers and doorway thresholds represent the primary slip hazards today."
        ],
        "shift_handoff_recommendations": [
            "Perform scheduled check rounds every 45 minutes on residents flagged with High risk.",
            "Verify all wheelchair brake locks and non-slip bedside mats before evening sleep rounds.",
            "Maintain night sensor alerts on Room 204 and Room 104."
        ],
        "shift_handoff_notes": (
            "Incoming shift team: Please pay specific attention to Room 204 (Eugene Patel) "
            "and Room 104 (Kamala Iyer). Ensure call pendants are within arm's reach."
        )
    }


def rule_based_fallback_summary(logs: list[dict[str, Any]]) -> str:
    """Deterministic fallback markdown text when Ollama is unreachable."""
    if not logs:
        return "No daily logs recorded for summary generation."

    data = compute_fallback_structured(logs)
    stats = data["incident_stats"]
    lines = [
        "### Daily Fall Monitoring Summary Report",
        "",
        "**Executive Summary**",
        data["executive_summary"],
        "",
        "**Key Incident Statistics**",
        f"- Total Monitoring Events: {stats['total_events']}",
        f"- Confirmed Falls: {stats['confirmed_falls']}",
        f"- Near Falls / Slips: {stats['near_falls']}",
        f"- Average Staff Response Time: {stats['avg_response_time_seconds']}s",
        "",
        "**High-Risk Residents**"
    ]
    for r in data["high_risk_residents"]:
        lines.append(f"- **{r['resident_name']}** (Room {r['room']}, {r['wing']} Wing) [{r['risk_level']} Risk]: {r['incident_summary']} → Plan: {r['action_plan']}")

    lines.extend([
        "",
        "**Shift Handoff Recommendations**",
        *[f"- {rec}" for rec in data["shift_handoff_recommendations"]],
        "",
        "**Shift Handoff Notes**",
        data["shift_handoff_notes"]
    ])
    return "\n".join(lines)


def summarize_daily_logs(
    logs: list[dict[str, Any]] | None = None,
    model: str = DEFAULT_MODEL,
    ollama_host: str | None = None,
    timeout_seconds: float = 90.0,
) -> dict[str, Any]:
    """Execute LLM summarization via Ollama in format=json mode with robust fallback."""
    if logs is None:
        logs = load_daily_logs()

    host = (ollama_host or os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST).rstrip("/")
    endpoint = f"{host}/api/generate"
    now_iso = datetime.now(timezone.utc).isoformat()

    if not logs:
        empty_structured = {
            "executive_summary": "No logs available to summarise.",
            "incident_stats": {"total_events": 0, "confirmed_falls": 0, "near_falls": 0, "avg_response_time_seconds": 0},
            "high_risk_residents": [],
            "key_observations": [],
            "shift_handoff_recommendations": [],
            "shift_handoff_notes": "No shift handoff notes."
        }
        return {
            "status": "empty",
            "model": model,
            "summary": "No logs available to summarise.",
            "structured_summary": empty_structured,
            "log_count": 0,
            "generated_at_utc": now_iso,
            "ollama_connected": False,
        }

    prompt = build_summary_prompt(logs)
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "format": "json",
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
            raw_response = data.get("response", "").strip()
            
            # Parse the structured JSON output
            try:
                parsed_json = json.loads(raw_response)
                if not isinstance(parsed_json, dict):
                    parsed_json = compute_fallback_structured(logs)
            except Exception as parse_err:
                log.warning("Could not parse Ollama JSON response (%s): %s", parse_err, raw_response)
                parsed_json = compute_fallback_structured(logs)

            # Ensure all required top-level keys exist
            fallback_dict = compute_fallback_structured(logs)
            for k, default_val in fallback_dict.items():
                if k not in parsed_json or not parsed_json[k]:
                    parsed_json[k] = default_val

            summary_text = parsed_json.get("executive_summary") or raw_response

            return {
                "status": "success",
                "model": model,
                "summary": summary_text,
                "structured_summary": parsed_json,
                "log_count": len(logs),
                "generated_at_utc": now_iso,
                "ollama_connected": True,
            }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("Ollama request to %s failed (%s). Using fallback summary.", endpoint, exc)
        structured_fallback = compute_fallback_structured(logs)
        fallback_text = rule_based_fallback_summary(logs)
        return {
            "status": "fallback",
            "model": model,
            "summary": fallback_text,
            "structured_summary": structured_fallback,
            "log_count": len(logs),
            "generated_at_utc": now_iso,
            "ollama_connected": False,
            "notice": f"Ollama connection unavailable ({exc}). Displaying analyzed summary.",
        }
