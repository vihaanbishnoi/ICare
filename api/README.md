# API jobs and incidents

Person 2's FastAPI service under /api/v1, implementing [API v1](../docs/interfaces/api.md)
against the [engine v1](../docs/interfaces/inference.md) boundary. Read
[Person 2](../docs/team/person_2.md) and the [stack](../docs/project/stack.md) for scope.

Status: first slice (P2A/P2B with parts of P2C/P2D). All v1 routes exist and are
tested with labelled test adapters. No real model has run through this API yet,
because Person 1's `icare_app.engine` does not exist. Until it does, `/ready` and
job creation return 503 `model_unavailable`; the API never substitutes a fake engine.

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
| engine.py | Engine protocol and loader for Person 1's engine |
| config.py | Limits and paths, overridable by environment |

Runtime data goes to `artifacts/api/` (ignored): `icare.sqlite3` and one random
folder per job holding `source.mp4` (uploads only), `result.json`, `report.json`,
`report.csv`.

## Decisions for review

- **Ownership:** an opaque random `icare_session` cookie (HttpOnly, SameSite=Strict,
  Secure when `ICARE_COOKIE_SECURE=1`, path /api/v1). Only its SHA-256 is stored.
  Unknown and not-owned jobs both return 404.
- **Origin check:** POST/DELETE with an `Origin` header must match the request host
  or `ICARE_ALLOWED_ORIGINS`, else 403 `bad_origin`. 403 is not in the v1 error
  list; Person 5 please confirm.
- **DELETE /jobs/{id}:** queued or running returns 200 with the Job (cancel
  requested; poll until `cancelled`). A finished job is deleted with its files: 204.
- **Progress:** engine progress is capped at 0.99; 1.0 only after results are written.
- **Engine output is validated, not repaired.** A probability outside [0,1] or a
  malformed pose fails the job with `invalid_engine_output` instead of being clipped.
- **CSV report:** one row per prediction, with `incident_id` filled on the
  prediction that opened an incident. JSON report is the full Result document.
- **Retention:** finished jobs older than 24 h are removed at startup and on each
  new job. Jobs left queued/running by a crash fail as `interrupted` on restart.
- **Rate limit:** only queue capacity (429 `capacity`, five queued) is enforced.
  A per-visitor rate limit waits for Person 5's host measurement.

## Limits (env override)

| Setting | Default | Env |
| --- | --- | --- |
| Upload size | 50 MB | ICARE_MAX_UPLOAD_MB |
| Upload duration | 60 s | ICARE_MAX_UPLOAD_SECONDS |
| Queued jobs | 5 | ICARE_MAX_QUEUED_JOBS |
| Job timeout | 600 s | ICARE_JOB_TIMEOUT_SECONDS |
| Retention | 24 h | ICARE_RETENTION_HOURS |

## Handoff

**Person 1:** `api/engine.py` loads `icare_app.engine.load_engine(config)` with
`{"model_path", "device"}`. The engine needs `ready`, `model_version`, `close()`
and `analyze_video(path, *, on_pose, on_prediction, on_progress, cancel_event)`
returning `{"duration_seconds", "frame_width", "frame_height"}` (optional
`"metrics"` dict of measured numbers). Raise an exception with a string `code`
(`no_person`, `invalid_video`, ...) for distinct failures. `on_progress` raises
when the job is cancelled; check `cancel_event` between samples too.

**Person 3:** routes and fields follow API v1. Poll `GET /jobs/{id}` about once
a second until `completed`, `failed` or `cancelled`. Every error body is
`{"error": {"code", "message"}}`.

**Person 4:** examples are read from `examples/catalog.json`
(`ICARE_EXAMPLES_MANIFEST`): `{"examples": [ ...Example fields..., "file":
"relative/path.mp4" ]}`. The `file` path is never sent to the browser. Example
jobs currently run `on_demand`; cached analysis is not implemented yet.

**Person 5:** new deps in `api/requirements.txt` and API test deps added to
`requirements-test.txt`. Same-origin proxy must forward the Host header so the
origin check and cookie work.
