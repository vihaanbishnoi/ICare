"""API settings. Defaults are the v1 limits in docs/interfaces/api.md."""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    data_dir: Path = ROOT / "artifacts" / "api"
    examples_manifest: Path = ROOT / "examples" / "catalog.json"
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
    result_reserve_bytes: int = 5 * 1024 * 1024
    allow_unverified_examples: bool = False

    def __post_init__(self) -> None:
        for name in ('max_upload_bytes', 'max_upload_seconds', 'max_queued_jobs',
                     'job_timeout_seconds', 'retention_seconds', 'cleanup_interval_seconds',
                     'max_active_jobs_per_visitor', 'max_jobs_per_visitor_window',
                     'max_jobs_per_ip_window', 'admission_window_seconds', 'max_storage_bytes',
                     'result_reserve_bytes'):
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
            examples_manifest=Path(
                env.get("ICARE_EXAMPLES_MANIFEST", defaults.examples_manifest)
            ),
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
            allow_unverified_examples=env.get('ICARE_ALLOW_UNVERIFIED_EXAMPLES', '0') == '1',
        )
