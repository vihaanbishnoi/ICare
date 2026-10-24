"""Validated API limits and environment configuration."""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path


# Assets stay at the checkout root for local editable installs.
ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    data_dir: Path = ROOT / "artifacts" / "api"
    max_upload_bytes: int = 50 * 1024 * 1024
    max_upload_seconds: float = 60.0
    max_queued_jobs: int = 5
    job_timeout_seconds: float = 600.0
    retention_seconds: float = 24 * 3600.0
    cleanup_interval_seconds: float = 60.0
    cookie_secure: bool = False
    allowed_origins: tuple[str, ...] = ()
    max_active_jobs_per_visitor: int = 2
    max_jobs_per_visitor_window: int = 12
    max_jobs_per_ip_window: int = 60
    admission_window_seconds: float = 3600.0
    max_storage_bytes: int = 1024 * 1024 * 1024
    # Per-job result/report budget; poses grow with the number of people (~0.8 MB
    # per person per minute), so 16 MB covers about 20 people for a 60 s upload.
    result_reserve_bytes: int = 16 * 1024 * 1024
    # Consecutive P(Fall) >= 0.50 predictions per person before an incident (1 = baseline).
    fall_confirmations: int = 1

    def __post_init__(self) -> None:
        for name in ('max_upload_bytes', 'max_upload_seconds', 'max_queued_jobs',
                     'job_timeout_seconds', 'retention_seconds', 'cleanup_interval_seconds',
                     'max_active_jobs_per_visitor', 'max_jobs_per_visitor_window',
                     'max_jobs_per_ip_window', 'admission_window_seconds', 'max_storage_bytes',
                     'result_reserve_bytes', 'fall_confirmations'):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be positive and finite')

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        defaults = cls()
        origins = env.get("ICARE_ALLOWED_ORIGINS", "")
        return cls(
            data_dir=Path(env.get("ICARE_API_DATA_DIR", defaults.data_dir)),
            max_upload_bytes=int(
                float(env.get("ICARE_MAX_UPLOAD_MB", 50)) * 1024 * 1024
            ),
            max_upload_seconds=float(env.get("ICARE_MAX_UPLOAD_SECONDS", 60)),
            max_queued_jobs=int(env.get("ICARE_MAX_QUEUED_JOBS", 5)),
            job_timeout_seconds=float(env.get("ICARE_JOB_TIMEOUT_SECONDS", 600)),
            retention_seconds=float(env.get("ICARE_RETENTION_HOURS", 24)) * 3600,
            cleanup_interval_seconds=float(env.get("ICARE_CLEANUP_INTERVAL_SECONDS", 60)),
            cookie_secure=env.get("ICARE_COOKIE_SECURE", "0") == "1",
            allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
            max_active_jobs_per_visitor=int(env.get('ICARE_MAX_ACTIVE_JOBS_PER_VISITOR', 2)),
            max_jobs_per_visitor_window=int(env.get('ICARE_MAX_JOBS_PER_VISITOR_WINDOW', 12)),
            max_jobs_per_ip_window=int(env.get('ICARE_MAX_JOBS_PER_IP_WINDOW', 60)),
            admission_window_seconds=float(env.get('ICARE_ADMISSION_WINDOW_SECONDS', 3600)),
            max_storage_bytes=int(float(env.get('ICARE_MAX_STORAGE_MB', 1024)) * 1024 * 1024),
            fall_confirmations=int(env.get('ICARE_FALL_CONFIRMATIONS', 1)),
            result_reserve_bytes=int(float(env.get('ICARE_RESULT_BUDGET_MB', 16)) * 1024 * 1024),
        )
