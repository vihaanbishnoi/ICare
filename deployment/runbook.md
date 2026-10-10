# Deployment runbook

Owner: Deployment owner (Person 5). Updated 10 October 2026. Unverified items remain pending.

| Field | Current value |
| --- | --- |
| Provider / account / project / cost ceiling | Pending selection |
| Staging / public HTTPS URL | Pending |
| Local API | python -m uvicorn api.main:create_app --factory --host 127.0.0.1 --port 8000 |
| Local frontend | frontend/: npm ci, npm run dev with Node 24+ |
| Containers | root compose.yaml; config validated, build/run pending |
| Engine | ONNX Runtime CPU, one active job, class order No Fall / Fall |
| Model release | Readiness/results include weight hash; record full hash/commit at deployment |
| Limits | 50 MB / 60 s, five queued jobs, 600 s timeout; visitor/network/storage budgets implemented; host tuning pending |
| Retention | Terminal jobs expire 24 h after creation; cleanup every 60 s; active jobs preserved |
| Data / cache | Named volumes api-data and model-cache |
| Recovery owner / backup / rollback tag | Pending named teammates and tested procedure |

## First container verification

1. Start Docker and run docker compose config --quiet, then docker compose up --build.
2. Allow initial pose-model downloads; inspect docker compose logs api if startup fails.
3. Confirm /api/v1/health and /api/v1/ready at http://127.0.0.1:7860.
4. Run both examples and a short upload. Check overlays, timeline, incidents,
   JSON/CSV downloads and seeking; verify a second visitor gets 404.
5. Check measured RAM/CPU, resource caps, queue saturation, timeout, invalid media,
   expiry, cancellation and restart recovery. Record evidence and versions.

API installs requirements.txt plus api/requirements.txt. RTMLib currently depends
on overlapping OpenCV distributions; verify and lock the actual image rather
than assuming the test-only headless environment is the product.

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

Monitor disk usage, failed jobs, model-cache availability and resource/cost caps.
Back up SQLite consistently and private files according to the host privacy policy;
exact backup/restore commands remain pending. Preserve volumes during rebuilds.
Never include user uploads in a public repository or image.

## Rollback and publish

Record previous/current release commits/images, model hashes and configuration.
Test rollback on staging with preserved data and schema compatibility. Exact
rollback commands remain pending the host/image strategy. Deployment owner (Person 5) publishes the
live URL and demo recording after acceptance; Development supply evidence.
