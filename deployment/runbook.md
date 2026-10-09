# Product deployment runbook

Person 5 fills tested procedures as the five parts integrate. Pending values are
not configuration or evidence of deployment.

| Field | Verified value |
| --- | --- |
| Hosting provider/account/project | Pending Person 5's selection |
| Staging URL | Pending |
| Public no-login demo URL | Pending |
| Runtime/API/frontend startup | API + engine: `docker compose -f deployment/compose.yaml up --build -d` (see [README](README.md)); frontend pending |
| Release commit/model/configuration | Pending |
| Deployment/recovery owner and backup | Chosen teammates pending |
| Cost cap and hosting limits | Pending |
| Measured concurrency/latency/resources | Pending Person 4's evidence |
| Upload bytes/duration/rate/queue limits | API defaults 50 MB / 60 s / 5 queued, set by `ICARE_*` in compose; per-visitor rate limit pending Person 2 |
| Ownership/expiry/retention | HttpOnly session cookie, 24 h retention (API defaults); `ICARE_COOKIE_SECURE=1` required behind HTTPS |
| Secret store and variable names | Pending names only; never values |

## Deploy and verify

Local container (verified with `PRELOAD_MODELS=0`; see below):

```bash
docker compose -f deployment/compose.yaml up --build -d
curl -f http://127.0.0.1:8000/api/v1/health
curl -f http://127.0.0.1:8000/api/v1/ready      # must be 200 before announcing
curl -f http://127.0.0.1:8000/api/v1/examples
```

Pending: staging host deploy commands, the default `PRELOAD_MODELS=1` build on a
host that can reach the model URLs, and real example/upload outputs through the
deployed API/frontend.

## Monitor and recover

```bash
docker compose -f deployment/compose.yaml ps        # health: healthy
docker compose -f deployment/compose.yaml logs -f api
docker compose -f deployment/compose.yaml restart api
```

Job data persists in the `icare-data` volume across restarts; jobs left running
by a crash are marked `interrupted` on startup. `docker compose ... down -v`
deletes all job data. Pending: CPU/RAM/storage/cost limits and the responsible teammate.

## Roll back

Pending: previous release, exact rollback commands, artifact/configuration
compatibility, and staging evidence.

## Publish

Person 5 updates the live navigation, README, combined report, and demo recording
with the other parts' input. Do not transfer this work to the project owner.
