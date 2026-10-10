"""FastAPI app for /api/v1. Run with:

    uvicorn api.main:create_app --factory
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
from pathlib import Path
import secrets
import shutil
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from api.config import Settings
from api.engine import Engine, load_real_engine
from api.results import job_url
from api.schemas import Example, ExampleJobRequest, ExamplesResponse, Incident, Job
from api.store import ACTIVE_STATES, Store, utc_now
from api.video import InvalidVideo, mp4_duration_seconds
from api.worker import JobRunner


log = logging.getLogger(__name__)

SESSION_COOKIE = "icare_session"
CHUNK_BYTES = 1024 * 1024
_NOT_LOADED = object()


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


def not_found() -> ApiError:
    # Unknown and not-owned look identical, so job IDs cannot be probed.
    return ApiError(404, "not_found", "No such job for this browser session.")


def create_app(settings: Settings | None = None, engine: Any = _NOT_LOADED) -> FastAPI:
    """Build the app. Tests inject ``engine``; production loads Person 1's engine."""

    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state = app.state
        state.engine = load_real_engine() if engine is _NOT_LOADED else engine
        state.store = Store(settings.data_dir / "icare.sqlite3")
        state.store.fail_interrupted_jobs()
        state.store.reconcile_admissions(settings.data_dir / 'jobs')
        state.admission_salt = state.store.admission_salt()
        for folder in (settings.data_dir / 'jobs').glob('*'):
            if folder.is_dir() and state.store.get_job(folder.name) is None:
                remove_job_files(settings, folder.name)
        state.runner = JobRunner(
            state.store, state.engine, settings.data_dir / "jobs", settings.job_timeout_seconds,
            settings.result_reserve_bytes,
        )
        state.runner.start()
        remove_expired(state.store, settings)
        async def cleanup_loop():
            while True:
                await asyncio.sleep(max(1.0, settings.cleanup_interval_seconds))
                try:
                    remove_expired(state.store, settings)
                except Exception:
                    log.exception("Scheduled job cleanup failed")
        cleanup_task = asyncio.create_task(cleanup_loop())
        try:
            yield
        finally:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task
            state.runner.stop()
            state.store.close()
            if state.engine is not None:
                state.engine.close()

    app = FastAPI(title="ICare API", version="1", lifespan=lifespan)
    app.state.settings = settings

    @app.middleware("http")
    async def private_results_cache(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/jobs"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(400, "invalid_request", "The request body is not valid.")

    app.include_router(router, prefix="/api/v1")
    return app


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


# ---------- dependencies ----------

def owner(request: Request, response: Response) -> str:
    """Anonymous browser ownership: an opaque HttpOnly cookie, stored hashed."""

    token = request.cookies.get(SESSION_COOKIE)
    if not token or len(token) > 128:
        token = secrets.token_urlsafe(32)
        response.set_cookie(
            SESSION_COOKIE, token, httponly=True, samesite="strict",
            secure=request.app.state.settings.cookie_secure, path="/api/v1",
        )
    return hashlib.sha256(token.encode()).hexdigest()


def same_origin(request: Request) -> None:
    """Reject cross-site mutating requests. Browsers always send Origin on POST/DELETE."""

    origin = request.headers.get("origin")
    if origin is None:
        return  # non-browser clients; ownership is still enforced by the cookie
    allowed = set(request.app.state.settings.allowed_origins)
    allowed.add(str(request.base_url).rstrip("/"))
    if origin.rstrip("/") not in allowed:
        raise ApiError(403, "bad_origin", "Requests must come from the ICare site.")


def require_engine(request: Request) -> Engine:
    engine = request.app.state.engine
    if engine is None or not engine.ready:
        raise ApiError(503, "model_unavailable", "The fall-detection model is not ready.")
    if not request.app.state.runner.available:
        raise ApiError(503, "worker_unavailable", "The inference worker timed out. Please try again later.")
    return engine


def owned_job(job_id: str, request: Request, owner_key: str = Depends(owner)) -> dict:
    job = request.app.state.store.get_owned_job(job_id, owner_key)
    if job is None:
        raise not_found()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=request.app.state.settings.retention_seconds)
    if job["state"] not in ACTIVE_STATES and datetime.fromisoformat(job["created_at_utc"]) < cutoff:
        remove_job_files(request.app.state.settings, job_id)
        request.app.state.store.delete_job(job_id)
        raise not_found()
    return job


# ---------- helpers ----------

def job_document(job: dict) -> dict:
    error = None
    if job["error_code"]:
        error = {"code": job["error_code"], "message": job["error_message"]}
    return Job(
        job_id=job["job_id"],
        state=job["state"],
        progress=job["progress"],
        source_kind=job["source_kind"],
        created_at_utc=job["created_at_utc"],
        model_version=job["model_version"],
        result_url=job_url(job["job_id"], "/results") if job["state"] == "completed" else None,
        error=error,
    ).model_dump()


def load_examples(settings: Settings) -> list[dict]:
    """Person 4's approved catalogue; an empty list when none exists yet."""

    try:
        raw = json.loads(settings.examples_manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    examples = []
    root = settings.examples_manifest.parent.resolve()
    for entry in raw.get("examples", []):
        if not settings.allow_unverified_examples and not (
            entry.get('rights_status') == 'verified' and entry.get('source_url')
            and entry.get('license') and entry.get('label_status') == 'verified'
        ):
            continue
        document = Example.model_validate(entry).model_dump()
        candidate = (root / entry["file"]).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file() or candidate.suffix.lower() != ".mp4":
            log.warning("Skipping unavailable or invalid example %s", document["example_id"])
            continue
        document["file"] = candidate
        document["video_url"] = f"/api/v1/examples/{quote(document['example_id'], safe='')}/media"
        examples.append(document)
    return examples


def check_capacity(request: Request) -> None:
    store: Store = request.app.state.store
    if store.count_queued() >= request.app.state.settings.max_queued_jobs:
        raise ApiError(429, "capacity", "The demo is busy. Please try again shortly.")


def new_job(request: Request, owner_key: str, source_kind: str,
            media_path: Path, example_id: str | None = None, job_id: str | None = None) -> dict:
    job = {
        "job_id": job_id or secrets.token_urlsafe(16),
        "owner": owner_key,
        "state": "queued",
        "progress": None,
        "source_kind": source_kind,
        "example_id": example_id,
        "media_path": str(media_path),
        "created_at_utc": utc_now(),
        "model_version": None,
        "error_code": None,
        "error_message": None,
    }
    if not request.app.state.store.create_job_with_capacity(
        job, request.app.state.settings.max_queued_jobs
    ):
        remove_job_files(request.app.state.settings, job["job_id"])
        raise ApiError(429, "capacity", "The demo is busy. Please try again shortly.")
    request.app.state.runner.submit(job["job_id"])
    request.app.state.store.finish_admission(job['job_id'])
    return job


def reserve_job(request: Request, owner_key: str, source_kind: str) -> str:
    settings = request.app.state.settings
    remove_expired(request.app.state.store, settings)
    job_id = secrets.token_urlsafe(16)
    # Hash the trusted ASGI peer address with a private persisted salt; do not
    # accept arbitrary client X-Forwarded-For headers here.
    peer = request.client.host if request.client else 'unknown'
    ip_key = hmac.new(request.app.state.admission_salt.encode(), peer.encode(), hashlib.sha256).hexdigest()
    reserve = settings.result_reserve_bytes + (settings.max_upload_bytes if source_kind == 'upload' else 0)
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=settings.admission_window_seconds)).isoformat()
    code = request.app.state.store.reserve_admission(job_id, owner_key, ip_key, reserve, settings, cutoff)
    if code:
        raise ApiError(429, code, 'The demo has reached an admission or storage limit. Please try later.')
    return job_id


def job_dir(settings: Settings, job_id: str) -> Path:
    return settings.data_dir / "jobs" / job_id


def remove_job_files(settings: Settings, job_id: str) -> None:
    root = (settings.data_dir / "jobs").resolve()
    target = job_dir(settings, job_id).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError("Job cleanup must remain inside its storage directory.")
    shutil.rmtree(target, ignore_errors=True)


def remove_expired(store: Store, settings: Settings) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.retention_seconds)
    for job in store.expired_jobs(cutoff.isoformat()):
        remove_job_files(settings, job["job_id"])
        store.delete_job(job["job_id"])
    receipt_cutoff = (datetime.now(timezone.utc) - timedelta(seconds=settings.admission_window_seconds)).isoformat()
    store.prune_admissions(receipt_cutoff)


# ---------- routes ----------

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    engine = request.app.state.engine
    if engine is None or not engine.ready:
        return error_response(503, "model_unavailable", "The fall-detection model is not ready.")
    if not request.app.state.runner.available:
        return error_response(503, "worker_unavailable", "The inference worker has timed out.")
    return JSONResponse({"status": "ready", "model_version": engine.model_version})


@router.get("/examples", response_model=ExamplesResponse)
def examples(request: Request) -> dict:
    items = load_examples(request.app.state.settings)
    return {"examples": [{k: v for k, v in e.items() if k != "file"} for e in items]}


@router.get("/examples/{example_id}/media")
def example_media(example_id: str, request: Request) -> FileResponse:
    match = [entry for entry in load_examples(request.app.state.settings) if entry["example_id"] == example_id]
    if not match:
        raise ApiError(404, "not_found", "No example has that ID.")
    return FileResponse(match[0]["file"], media_type="video/mp4")


@router.post("/jobs/example", status_code=202, dependencies=[Depends(same_origin)])
def create_example_job(body: ExampleJobRequest, request: Request,
                       owner_key: str = Depends(owner)) -> dict:
    require_engine(request)
    settings: Settings = request.app.state.settings
    match = [e for e in load_examples(settings) if e["example_id"] == body.example_id]
    if not match:
        raise ApiError(404, "not_found", "No approved example has that ID.")
    job_id = reserve_job(request, owner_key, 'example')
    try:
        job_dir(settings, job_id).mkdir(parents=True)
        # Public example media is read in place; never deleted with the job.
        job = new_job(request, owner_key, "example", match[0]["file"], body.example_id, job_id)
    except BaseException:
        remove_job_files(settings, job_id)
        request.app.state.store.finish_admission(job_id, 0)
        raise
    return job_document(job)


@router.post("/jobs/upload", status_code=202, dependencies=[Depends(same_origin)])
async def create_upload_job(request: Request,
                            owner_key: str = Depends(owner)) -> dict:
    require_engine(request)
    settings: Settings = request.app.state.settings
    # Admission runs before parsing/spooling multipart content. Bound the entire
    # streamed body as well as the extracted file, including chunked requests.
    job_id = reserve_job(request, owner_key, 'upload')
    folder = job_dir(settings, job_id)
    media_path = folder / "source.mp4"
    form = None
    received = 0
    async def bounded_receive():
        nonlocal received
        message = await request.receive()
        received += len(message.get('body', b''))
        if received > settings.max_upload_bytes + 1024 * 1024:
            # Multipart parser catches this type and closes its temporary files.
            raise MultiPartException('Upload request exceeds its byte limit.')
        return message
    bounded_request = Request(request.scope, receive=bounded_receive)
    try:
        content_length = request.headers.get('content-length')
        if content_length:
            try:
                if int(content_length) > settings.max_upload_bytes + 1024 * 1024:
                    raise ApiError(413, 'file_too_large', 'The upload request is too large.')
            except ValueError:
                raise ApiError(400, 'invalid_request', 'Invalid content length.')
        try:
            form = await bounded_request.form(max_files=1, max_fields=0)
        except HTTPException as exc:
            if received > settings.max_upload_bytes + 1024 * 1024:
                raise ApiError(413, 'file_too_large', 'The upload request is too large.') from exc
            raise ApiError(400, 'invalid_request', 'Supply exactly one MP4 file in the file field.') from exc
        file = form.get('file')
        if not isinstance(file, UploadFile) or len(form.multi_items()) != 1:
            raise ApiError(400, 'invalid_request', 'Supply exactly one MP4 file in the file field.')
        folder.mkdir(parents=True)
        size = 0
        with media_path.open("wb") as out:
            while chunk := await file.read(CHUNK_BYTES):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    limit = settings.max_upload_bytes // (1024 * 1024)
                    raise ApiError(413, "file_too_large", f"Videos must be {limit} MB or smaller.")
                out.write(chunk)
        try:
            duration = mp4_duration_seconds(media_path)
        except InvalidVideo as exc:
            raise ApiError(400, "invalid_video", f"{exc} Upload an MP4 video.") from exc
        if duration > settings.max_upload_seconds:
            raise ApiError(400, "video_too_long",
                           f"Videos must be {settings.max_upload_seconds:g} seconds or shorter.")
        request.app.state.store.resize_admission(job_id, size + settings.result_reserve_bytes)
        job = new_job(request, owner_key, "upload", media_path, job_id=job_id)
    except BaseException:
        remove_job_files(settings, job_id)
        request.app.state.store.finish_admission(job_id, 0)
        raise
    finally:
        if form is not None:
            await form.close()
    return job_document(job)


@router.get("/jobs/{job_id}")
def get_job(job: dict = Depends(owned_job)) -> dict:
    return job_document(job)


@router.get("/jobs/{job_id}/results")
def get_results(request: Request, job: dict = Depends(owned_job)) -> FileResponse:
    if job["state"] != "completed":
        raise ApiError(409, "not_complete", f"The job is {job['state']}, not completed.")
    path = job_dir(request.app.state.settings, job["job_id"]) / "result.json"
    return FileResponse(path, media_type="application/json")


@router.get("/jobs/{job_id}/media")
def get_media(job: dict = Depends(owned_job)) -> FileResponse:
    path = Path(job["media_path"])
    if not path.is_file():
        raise not_found()
    return FileResponse(path, media_type="video/mp4")  # Starlette handles Range


@router.get("/jobs/{job_id}/incidents/{incident_id}")
def get_incident(incident_id: str, request: Request, job: dict = Depends(owned_job)) -> dict:
    incident = request.app.state.store.get_incident(job["job_id"], incident_id)
    if incident is None:
        raise ApiError(404, "not_found", "No such incident for this job.")
    return Incident.model_validate(incident).model_dump()


@router.get("/jobs/{job_id}/reports/{report_format}")
def get_report(report_format: str, request: Request,
               job: dict = Depends(owned_job)) -> FileResponse:
    if report_format not in ("json", "csv"):
        raise ApiError(400, "invalid_format", "Report format must be json or csv.")
    if job["state"] != "completed":
        raise ApiError(409, "not_complete", f"The job is {job['state']}, not completed.")
    path = job_dir(request.app.state.settings, job["job_id"]) / f"report.{report_format}"
    media_type = "application/json" if report_format == "json" else "text/csv"
    return FileResponse(path, media_type=media_type,
                        filename=f"icare-report-{job['job_id'][:8]}.{report_format}")


@router.delete("/jobs/{job_id}", dependencies=[Depends(same_origin)])
def delete_job(request: Request, job: dict = Depends(owned_job)) -> Response:
    """Active job: cancel it and return the Job. Finished job: delete it (204)."""

    store: Store = request.app.state.store
    settings: Settings = request.app.state.settings
    if job["state"] in ACTIVE_STATES:
        # A running job stops at the engine's next cancel check; the client keeps
        # polling until the state is cancelled, then may DELETE again to remove it.
        request.app.state.runner.cancel(job["job_id"])
        return JSONResponse(job_document(store.get_job(job["job_id"])), status_code=200)
    remove_job_files(settings, job["job_id"])
    store.delete_job(job["job_id"])
    return Response(status_code=204)
