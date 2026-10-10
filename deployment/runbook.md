# Deployment runbook

Owner: Deployment owner (Person 5). Updated 10 October 2026. Unverified items remain pending.

| Field | Current value |
| --- | --- |
| Provider / account / project / cost ceiling | Pending selection |
| Staging / public HTTPS URL | Pending |
| Local API | python -m uvicorn api.main:create_app --factory --host 127.0.0.1 --port 8000 |
| Local frontend | frontend/: npm ci, npm run dev with Node 24+ |
| Containers | root compose.yaml; local build, run and deployment/smoke_test.sh verified 10 Oct 2026; CI repeats them |
| Engine | ONNX Runtime CPU, one active job, class order No Fall / Fall |
| Model release | Readiness/results include weight hash; record full hash/commit at deployment |
| Limits | 50 MB / 60 s, five queued jobs, 600 s timeout; visitor/network/storage budgets implemented; host tuning pending |
| Retention | Terminal jobs expire 24 h after creation; cleanup every 60 s; active jobs preserved |
| Data / cache | Named volume api-data (SQLite + job files); pose weights baked into the API image |
| Recovery owner / backup / rollback tag | Pending named teammates and tested procedure |

## First container verification

1. `ICARE_ALLOW_UNVERIFIED_EXAMPLES=1 docker compose up --build -d --wait`
   (the build downloads pose weights once; the container then starts ready).
2. `deployment/smoke_test.sh` - health, readiness, frontend, a real example job,
   results, CSV, range media, second-visitor 404 and cross-origin 403.
3. In a browser at http://127.0.0.1:7860, run both examples and a short upload;
   check overlays, timeline, incidents, downloads, seeking and phone width.
4. Done locally on 10 Oct 2026, also: invalid MP4 400, >50 MB 413, cancellation
   then model reload, `docker compose restart api` with results preserved.
5. Still to do on the real host: queue saturation, timeout, expiry, measured
   CPU/RAM under load. Record evidence and versions here.

The image installs deployment/requirements-runtime.txt (single headless OpenCV)
plus rtmlib `--no-deps`; the CI job asserts only `opencv-python-headless` exists.
Root requirements.txt remains the local development environment.

## HTTPS staging and release

Configure TLS and the public domain. Forward original Host and HTTPS protocol
to the internal nginx/API path; set API ICARE_COOKIE_SECURE=1. Keep API private.
Confirm Origin checks and secure cookies in the browser. Set host-specific
per-visitor/storage/cost limits and repeat tests through HTTPS. Record exact
host commands, account/project, URLs and costs here after testing.

## Monitor and recover

Use docker compose ps and docker compose logs --tail 100 api web for diagnostics.
Health checks detect readiness failures but do not themselves restart an unhealthy
process. Timeout terminates the isolated model process; readiness is unavailable during
automatic reload. Diagnose persistent reload failure before operator restart. Diagnose first, then docker compose restart
api restarts the worker; interrupted jobs fail on startup. Test recovery in
containers before release.

Monitor disk usage, failed jobs and resource/cost caps.
Back up SQLite consistently and private files according to the host privacy policy;
exact backup/restore commands remain pending. Preserve volumes during rebuilds.
Never include user uploads in a public repository or image.

## Rollback and publish

Record previous/current release commits/images, model hashes and configuration.
Test rollback on staging with preserved data and schema compatibility. Exact
rollback commands remain pending the host/image strategy. Deployment owner (Person 5) publishes the
live URL and demo recording after acceptance; Development supply evidence.
