"""FastAPI app for /api/v1. Run with:

    uvicorn icare.api.main:create_app --factory
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import logging
from pathlib import Path
import secrets
import shutil
import time
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from icare.api.clips import ClipManager
from icare.api.config import Settings
from icare.api.engine import Engine, load_real_engine
from icare.api.results import job_url
from icare.api.schemas import Clip, ClipList, Incident, Job
from icare.api.schemas import LiveFrame, LiveHistoryResponse, LiveSession
from icare.api.store import ACTIVE_STATES, Store, utc_now
from icare.api.video import InvalidVideo, mp4_duration_seconds
from icare.api.worker import JobRunner
from icare.api.live import LiveError, LiveManager, MAX_FRAME_BYTES


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
    """Build the app. Tests inject ``engine``; production loads the isolated model process."""

    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state = app.state
        state.engine = load_real_engine() if engine is _NOT_LOADED else engine
        state.store = Store(settings.data_dir / "icare.sqlite3")
        state.store.fail_interrupted_jobs()
        state.store.reconcile_admissions(settings.data_dir / 'jobs')
        state.admission_salt = state.store.admission_salt()
        state.clips = ClipManager.from_settings(state.store, settings)
        state.clips.startup()
        state.live = LiveManager(state.store, state.engine, settings, state.clips)
        for folder in (settings.data_dir / 'jobs').glob('*'):
            if folder.is_dir() and state.store.get_job(folder.name) is None:
                remove_job_files(settings, folder.name)
                state.clips.delete_for_source(folder.name)
        state.runner = JobRunner(
            state.store, state.engine, settings.data_dir / "jobs", settings.job_timeout_seconds,
            settings.result_reserve_bytes, settings.fall_confirmations, state.clips,
        )
        state.runner.start()
        remove_expired(state.store, settings, state.clips)
        async def cleanup_loop():
            last_cleanup = time.monotonic()
            while True:
                await asyncio.sleep(min(2.0, settings.cleanup_interval_seconds))
                try:
                    await asyncio.to_thread(state.live.expire)
                    if time.monotonic() - last_cleanup >= settings.cleanup_interval_seconds:
                        remove_expired(state.store, settings, state.clips)
                        last_cleanup = time.monotonic()
                except Exception:
                    log.exception("Scheduled job cleanup failed")
        cleanup_task = asyncio.create_task(cleanup_loop())
        try:
            yield
        finally:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task
            await asyncio.to_thread(state.live.close)
            state.runner.stop()
            await asyncio.to_thread(state.clips.close)
            state.store.close()
            if state.engine is not None:
                state.engine.close()

    app = FastAPI(title="ICare API", version="1", lifespan=lifespan)
    app.state.settings = settings

    @app.middleware("http")
    async def private_results_cache(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(("/api/v1/jobs", "/api/v1/live", "/api/v1/clips")):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(LiveError)
    async def live_error(request: Request, exc: LiveError) -> JSONResponse:
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
        request.app.state.clips.delete_for_source(job_id)
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


def new_job(request: Request, owner_key: str,
            media_path: Path, job_id: str | None = None) -> dict:
    job = {
        "job_id": job_id or secrets.token_urlsafe(16),
        "owner": owner_key,
        "state": "queued",
        "progress": None,
        "source_kind": "upload",
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


def reserve_job(request: Request, owner_key: str) -> str:
    settings = request.app.state.settings
    remove_expired(request.app.state.store, settings, request.app.state.clips)
    job_id = secrets.token_urlsafe(16)
    # Hash the trusted ASGI peer address with a private persisted salt; do not
    # accept arbitrary client X-Forwarded-For headers here.
    peer = request.client.host if request.client else 'unknown'
    ip_key = hmac.new(request.app.state.admission_salt.encode(), peer.encode(), hashlib.sha256).hexdigest()
    reserve = settings.result_reserve_bytes + settings.max_upload_bytes
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=settings.admission_window_seconds)).isoformat()
    with request.app.state.live.lock:
        request.app.state.live.ensure_video_allowed()
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


def remove_expired(store: Store, settings: Settings, clips: ClipManager | None = None) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.retention_seconds)
    for job in store.expired_jobs(cutoff.isoformat()):
        remove_job_files(settings, job["job_id"])
        if clips is not None:
            clips.delete_for_source(job["job_id"])
        store.delete_job(job["job_id"])
    if clips is not None:
        clips.remove_expired()  # clips keep their own 24 h clock
    receipt_cutoff = (datetime.now(timezone.utc) - timedelta(seconds=settings.admission_window_seconds)).isoformat()
    store.prune_admissions(receipt_cutoff)
    store.prune_live_history(cutoff.isoformat())


# ---------- routes ----------

router = APIRouter()


@router.post('/live/sessions', status_code=201, response_model=LiveSession, dependencies=[Depends(same_origin)])
def start_live(request: Request, owner_key: str = Depends(owner)) -> dict:
    require_engine(request)
    return request.app.state.live.start(owner_key)


@router.post('/live/sessions/{session_id}/frames', response_model=LiveFrame, dependencies=[Depends(same_origin)])
async def live_frame(session_id: str, timestamp_seconds: float, request: Request,
                     owner_key: str = Depends(owner)) -> dict:
    manager = request.app.state.live
    ticket = manager.claim(session_id, owner_key, timestamp_seconds)
    failure = None
    try:
        if request.headers.get('content-type', '').split(';')[0] != 'image/jpeg':
            raise LiveError(400, 'invalid_frame', 'Camera frames must use image/jpeg.')
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_FRAME_BYTES:
                raise LiveError(413, 'frame_too_large', 'Camera frames must be at most 1 MB.')
            data.extend(chunk)
        return await asyncio.to_thread(manager.process, ticket, bytes(data), timestamp_seconds)
    except LiveError as error:
        failure = error
        raise
    finally:
        manager.release(ticket)
        if failure is not None and failure.status >= 500:
            await asyncio.to_thread(manager.stop, session_id, owner_key, error=failure.message)


@router.delete('/live/sessions/{session_id}', dependencies=[Depends(same_origin)])
def stop_live(session_id: str, request: Request, owner_key: str = Depends(owner)) -> dict:
    # Idempotent stop reveals no information about another browser's session.
    request.app.state.live.stop(session_id, owner_key)
    return {'state': 'stopped'}


@router.get('/live/history', response_model=LiveHistoryResponse)
def live_history(request: Request, owner_key: str = Depends(owner)) -> dict:
    sessions = request.app.state.store.live_history(owner_key)
    with request.app.state.live.lock:
        active = request.app.state.live.session
        for session in sessions:
            if active is not None and active['session_id'] == session['session_id'] and active['owner'] == owner_key:
                session['frames_processed'] = active['frames']
    return {'sessions': sessions}


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


@router.post("/jobs/upload", status_code=202, dependencies=[Depends(same_origin)])
async def create_upload_job(request: Request,
                            owner_key: str = Depends(owner)) -> dict:
    require_engine(request)
    settings: Settings = request.app.state.settings
    # Admission runs before parsing/spooling multipart content. Bound the entire
    # streamed body as well as the extracted file, including chunked requests.
    job_id = reserve_job(request, owner_key)
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
        job = new_job(request, owner_key, media_path, job_id=job_id)
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
    request.app.state.clips.delete_for_source(job["job_id"])
    store.delete_job(job["job_id"])
    return Response(status_code=204)


# ---------- fall clips ----------

def owned_clip(clip_id: str, request: Request, owner_key: str = Depends(owner)) -> dict:
    row = request.app.state.clips.owned(clip_id, owner_key)
    if row is None:
        raise ApiError(404, "not_found", "No such clip for this browser session.")
    return row


@router.get("/clips", response_model=ClipList)
def list_clips(request: Request, owner_key: str = Depends(owner)) -> dict:
    """This browser's fall clips, newest first, with the storage cap and expiry in force."""
    return request.app.state.clips.listing(owner_key)


@router.get("/clips/{clip_id}", response_model=Clip)
def get_clip(request: Request, clip: dict = Depends(owned_clip)) -> dict:
    return request.app.state.clips.document(clip)


@router.get("/clips/{clip_id}/video")
def get_clip_video(request: Request, clip: dict = Depends(owned_clip)) -> FileResponse:
    if clip["status"] == "pending":
        raise ApiError(409, "clip_pending", "The clip is still being saved.")
    path = request.app.state.clips.path_of(clip)
    if path is None:
        raise ApiError(404, "clip_unavailable", clip["error_message"] or "This clip is no longer available.")
    return FileResponse(path, media_type=clip["media_type"])  # Starlette handles Range


@router.delete("/clips/{clip_id}", status_code=204, dependencies=[Depends(same_origin)])
def delete_clip(request: Request, clip: dict = Depends(owned_clip)) -> Response:
    request.app.state.clips.delete(clip["clip_id"])
    return Response(status_code=204)
