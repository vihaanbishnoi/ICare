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
CREATE TABLE IF NOT EXISTS admissions (
    job_id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    ip_key TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    reserved_bytes INTEGER NOT NULL,
    pending INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS admissions_time ON admissions(created_at_utc);
CREATE TABLE IF NOT EXISTS service_settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
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

    def admission_salt(self) -> str:
        import secrets
        with self._lock:
            self._db.execute('INSERT OR IGNORE INTO service_settings VALUES (?, ?)',
                             ('admission_salt', secrets.token_hex(32)))
            self._db.commit()
            return self._db.execute('SELECT value FROM service_settings WHERE name = ?',
                                    ('admission_salt',)).fetchone()[0]

    def reserve_admission(self, job_id: str, owner: str, ip_key: str, reserved_bytes: int,
                          settings, cutoff: str) -> str | None:
        """Reserve queue/storage before receiving a body; receipts outlive deleted jobs."""
        with self._lock, self._db:
            # SQLite serializes admission even if callers use distinct connections.
            self._db.execute('BEGIN IMMEDIATE')
            rows = self._db.execute('SELECT * FROM admissions').fetchall()
            recent = [r for r in rows if r['created_at_utc'] >= cutoff]
            if sum(r['owner'] == owner for r in recent) >= settings.max_jobs_per_visitor_window:
                return 'visitor_rate_limit'
            if sum(r['ip_key'] == ip_key for r in recent) >= settings.max_jobs_per_ip_window:
                return 'network_rate_limit'
            active = self._db.execute("SELECT COUNT(*) FROM jobs WHERE owner=? AND state IN ('queued','running')", (owner,)).fetchone()[0]
            if active + sum(r['pending'] and r['owner'] == owner for r in rows) >= settings.max_active_jobs_per_visitor:
                return 'visitor_capacity'
            queued = self._db.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0]
            if queued + sum(r['pending'] for r in rows) >= settings.max_queued_jobs:
                return 'capacity'
            if sum(r['reserved_bytes'] for r in rows) + reserved_bytes > settings.max_storage_bytes:
                return 'storage_capacity'
            self._db.execute('INSERT INTO admissions VALUES (?, ?, ?, ?, ?, 1)',
                             (job_id, owner, ip_key, utc_now(), reserved_bytes))
        return None

    def finish_admission(self, job_id: str, reserved_bytes: int | None = None) -> None:
        if reserved_bytes is None:
            self._write('UPDATE admissions SET pending=0 WHERE job_id=?', (job_id,))
        else:
            self._write('UPDATE admissions SET pending=0, reserved_bytes=? WHERE job_id=?',
                        (reserved_bytes, job_id))

    def resize_admission(self, job_id: str, reserved_bytes: int) -> None:
        self._write('UPDATE admissions SET reserved_bytes=? WHERE job_id=?', (reserved_bytes, job_id))

    def reconcile_admissions(self, jobs_dir: Path) -> None:
        """Recover reservations after crash/upgrade and account for existing files."""
        with self._lock, self._db:
            self._db.execute('UPDATE admissions SET pending=0, reserved_bytes=0 WHERE job_id NOT IN (SELECT job_id FROM jobs)')
            for job in self._db.execute('SELECT * FROM jobs').fetchall():
                folder = jobs_dir / job['job_id']
                size = sum(p.stat().st_size for p in folder.glob('*') if p.is_file())
                self._db.execute('INSERT OR IGNORE INTO admissions VALUES (?, ?, ?, ?, ?, 0)',
                                 (job['job_id'], job['owner'], '', job['created_at_utc'], size))

    def prune_admissions(self, cutoff: str) -> None:
        self._write('DELETE FROM admissions WHERE created_at_utc < ? AND reserved_bytes=0 AND pending=0', (cutoff,))

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

    def create_job_with_capacity(self, job: dict[str, Any], max_queued: int) -> bool:
        """Check capacity and insert atomically for concurrent callers."""
        columns = ", ".join(job)
        marks = ", ".join("?" for _ in job)
        return self._write(
            f"INSERT INTO jobs ({columns}) SELECT {marks} "
            "WHERE (SELECT COUNT(*) FROM jobs WHERE state = 'queued') < ?",
            (*job.values(), max_queued),
        ) == 1

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
        self.finish_admission(job_id, 0)

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
