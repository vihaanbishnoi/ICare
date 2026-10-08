"""SQLite metadata for jobs and incidents. Media/results live in per-job folders."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
from typing import Any


ACTIVE_STATES = ("queued", "running")
TERMINAL_STATES = ("completed", "failed", "cancelled")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    state TEXT NOT NULL,
    progress REAL,
    source_kind TEXT NOT NULL,
    example_id TEXT,
    media_path TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    model_version TEXT,
    error_code TEXT,
    error_message TEXT
);
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    detected_at_seconds REAL NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("PRAGMA foreign_keys = ON")
            self._db.executescript(SCHEMA)
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _write(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            cursor = self._db.execute(sql, params)
            self._db.commit()
            return cursor.rowcount

    def _read(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._db.execute(sql, params)]

    def create_job(self, job: dict[str, Any]) -> None:
        columns = ", ".join(job)
        marks = ", ".join("?" for _ in job)
        self._write(f"INSERT INTO jobs ({columns}) VALUES ({marks})", tuple(job.values()))

    def get_owned_job(self, job_id: str, owner: str) -> dict[str, Any] | None:
        rows = self._read(
            "SELECT * FROM jobs WHERE job_id = ? AND owner = ?", (job_id, owner)
        )
        return rows[0] if rows else None

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        rows = self._read("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        return rows[0] if rows else None

    def update_job(self, job_id: str, **fields: Any) -> None:
        assignments = ", ".join(f"{name} = ?" for name in fields)
        self._write(
            f"UPDATE jobs SET {assignments} WHERE job_id = ?",
            (*fields.values(), job_id),
        )

    def transition(self, job_id: str, from_states: tuple[str, ...], **fields: Any) -> bool:
        """Update only if the job is still in one of ``from_states``."""

        assignments = ", ".join(f"{name} = ?" for name in fields)
        marks = ", ".join("?" for _ in from_states)
        changed = self._write(
            f"UPDATE jobs SET {assignments} WHERE job_id = ? AND state IN ({marks})",
            (*fields.values(), job_id, *from_states),
        )
        return changed == 1

    def count_queued(self) -> int:
        return self._read("SELECT COUNT(*) AS n FROM jobs WHERE state = 'queued'")[0]["n"]

    def fail_interrupted_jobs(self) -> None:
        """Jobs left active by a previous process can never finish."""

        self._write(
            "UPDATE jobs SET state = 'failed', progress = NULL, "
            "error_code = 'interrupted', "
            "error_message = 'The server restarted before this job finished.' "
            "WHERE state IN ('queued', 'running')"
        )

    def expired_jobs(self, created_before_utc: str) -> list[dict[str, Any]]:
        return self._read(
            "SELECT * FROM jobs WHERE created_at_utc < ? AND state NOT IN (?, ?)",
            (created_before_utc, *ACTIVE_STATES),
        )

    def delete_job(self, job_id: str) -> None:
        self._write("DELETE FROM jobs WHERE job_id = ?", (job_id,))

    def add_incident(self, incident: dict[str, Any]) -> None:
        columns = ", ".join(incident)
        marks = ", ".join("?" for _ in incident)
        self._write(
            f"INSERT INTO incidents ({columns}) VALUES ({marks})",
            tuple(incident.values()),
        )

    def clear_incidents(self, job_id: str) -> None:
        self._write("DELETE FROM incidents WHERE job_id = ?", (job_id,))

    def get_incident(self, job_id: str, incident_id: str) -> dict[str, Any] | None:
        rows = self._read(
            "SELECT * FROM incidents WHERE job_id = ? AND incident_id = ?",
            (job_id, incident_id),
        )
        return rows[0] if rows else None
