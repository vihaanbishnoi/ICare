"""API settings. Defaults are the v1 limits in docs/interfaces/api.md."""
from __future__ import annotations

from dataclasses import dataclass
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
    cookie_secure: bool = False
    allowed_origins: tuple[str, ...] = ()

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
            cookie_secure=env.get("ICARE_COOKIE_SECURE", "0") == "1",
            allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        )
