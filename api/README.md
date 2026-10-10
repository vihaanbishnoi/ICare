# API jobs and incidents

Development's FastAPI service under /api/v1, implementing [API v1](../docs/interfaces/api.md)
against the [engine v1](../docs/interfaces/inference.md) boundary. Read
[Development](../docs/development.md) and the [stack](../docs/project/stack.md) for scope.

Status: v1 routes and the real `icare_app.engine` are implemented. Local CPU
fall/normal clips and browser uploads completed through this API. Unit tests also
use labelled adapters. `/ready` and submission return 503 when the model is not
ready or a timed-out worker remains stuck. See [verified status](../docs/project/implementation_status.md).

## Run

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r api/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api.main:create_app --factory --port 8000
```

Tests (no model needed): `python -m unittest discover -s tests -v`.

## Layout

| File | Responsibility |
| --- | --- |
| main.py | App factory, routes, cookie ownership, origin check, upload limits |
| worker.py | One worker thread, one job at a time, cancel and timeout |
| incidents.py | Incident rule: 0.50 trigger, re-arm after three predictions below 0.35 |
| store.py | SQLite job/incident metadata |
| results.py | Result document plus owned report.json/report.csv |
| video.py | MP4 content and duration check without decoding |
| engine.py | Engine protocol and loader for Development's engine |
| config.py | Limits and paths, overridable by environment |

Runtime data goes to `artifacts/api/` (ignored): `icare.sqlite3` and one random
folder per job holding `source.mp4` (uploads only), `result.json`, `report.json`,
`report.csv`.

## Decisions for review

- **Ownership:** an opaque random `icare_session` cookie (HttpOnly, SameSite=Strict,
  Secure when `ICARE_COOKIE_SECURE=1`, path /api/v1). Only its SHA-256 is stored.
  Unknown and not-owned jobs both return 404.
- **Origin check:** POST/DELETE with an `Origin` header must match the request host
  or `ICARE_ALLOWED_ORIGINS`, else 403 `bad_origin`. Preserve browser Host in
  the development and production proxies; do not rewrite it to the API host.
- **DELETE /jobs/{id}:** queued or running returns 200 with the Job (cancel
  requested; poll until `cancelled`). A finished job is deleted with its files: 204.
- **Progress:** engine progress is capped at 0.99; 1.0 only after results are written.
- **Engine output is validated, not repaired.** A probability outside [0,1] or a
  malformed pose fails the job with `invalid_engine_output` instead of being clipped.
  Keypoints must be exactly 17 triples of finite values. RTMPose joint scores
  are raw finite scores, not bounded fall probabilities.
- **CSV report:** one row per prediction, with `incident_id` filled on the
  prediction that opened an incident. JSON report is the full Result document.
- **Retention:** terminal jobs older than 24 h are removed at startup, new jobs,
  access and periodic cleanup (60 s default). Active jobs are retained. Job
  responses use `Cache-Control: private, no-store`. Interrupted jobs fail on restart.
- **Model isolation:** production loads the model in one spawned process. Parent
  cancellation terminates hung native calls, starts a new model process, and
  readiness stays unavailable during reload. Injected test adapters remain labelled.
- **Admission:** atomic visitor/network windows and active-job/queue/storage
  reservations run before multipart parsing. Limits survive result deletion;
  network identifiers are salted hashes of the trusted ASGI peer address.
- **Storage:** 1 GB job-file budget by default, with 5 MB reserved for result
  documents. Oversized results fail before writing. Failed/rejected uploads
  release their reservation; receipts retain the rate-limit window.
- **Recovery:** interrupted jobs fail on startup, reservations reconcile and
  orphan job folders are removed. Host-level backup/rollback remains deployment work.

## Limits (env override)

| Setting | Default | Env |
| --- | --- | --- |
| Upload size | 50 MB | ICARE_MAX_UPLOAD_MB |
| Upload duration | 60 s | ICARE_MAX_UPLOAD_SECONDS |
| Queued jobs | 5 | ICARE_MAX_QUEUED_JOBS |
| Job timeout | 600 s | ICARE_JOB_TIMEOUT_SECONDS |
| Retention | 24 h | ICARE_RETENTION_HOURS |
| Cleanup interval | 60 s | ICARE_CLEANUP_INTERVAL_SECONDS |

## Handoff

**Development:** `api/engine.py` loads `icare_app.engine.load_engine(config)` with
`{"model_path", "device"}`. The engine needs `ready`, `model_version`, `close()`
and `analyze_video(path, *, on_pose, on_prediction, on_progress, cancel_event)`
returning `{"duration_seconds", "frame_width", "frame_height"}` (optional
`"metrics"` dict of measured numbers). Raise an exception with a string `code`
(`no_person`, `invalid_video`, ...) for distinct failures. `on_progress` raises
when the job is cancelled; check `cancel_event` between samples too.

**Development:** routes and fields follow API v1. Poll `GET /jobs/{id}` about once
a second until `completed`, `failed` or `cancelled`. Every error body is
`{"error": {"code", "message"}}`.

**Development:** examples are read from `examples/catalog.json`
(`ICARE_EXAMPLES_MANIFEST`): `{"examples": [ ...Example fields..., "file":
"relative/path.mp4" ]}`. The `file` path is never sent to the browser. Example
jobs currently run `on_demand`; cached analysis is not implemented yet.
Public catalog media is served at `GET /examples/{example_id}/media` with range
support. Only existing MP4 files inside the catalog directory are exposed; paths
outside it are excluded. Verify catalog provenance/rights before public hosting.

**Deployment owner (Person 5):** new deps in `api/requirements.txt` and API test deps added to
`requirements-test.txt`. Same-origin proxy must forward the Host header so the
origin check and cookie work.

Only examples with verified rights, source URL, license and independent label
status are exposed by default. Existing diagnostic clips are quarantined from
public exposure. Set ICARE_ALLOW_UNVERIFIED_EXAMPLES=1 only for local diagnostics.
See .env.example for visitor/network/storage variables.
