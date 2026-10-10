# Deployment and release

Deployment owner (Person 5) owns integration, hosting, HTTPS, cost limits, recovery and release
documentation. See the [current status](../docs/project/implementation_status.md)
and [runbook](runbook.md). There is no verified public deployment yet.

## Local packaging

With a running Docker daemon, from the repository root:

```powershell
docker compose config --quiet
docker compose up --build
```

The planned local URL is http://127.0.0.1:7860. Configuration validation passed;
images were not built/run here because the Docker daemon was unavailable.
Treat the first clean build and real example/upload check as a release task.

- Dockerfile.api installs the CPU runtime/API, runs as an unprivileged user,
  and starts one uvicorn process. API port 8000 is internal to Compose.
- Dockerfile.web builds/tests React and serves dist through nginx.
- nginx preserves Host, proxies /api/v1 and serves SPA routes on the same origin.
- Named volumes persist private job data and downloaded pose weights.
- API resources default to two CPUs / 2 GB; these are initial limits, not measured
  adequate capacity. First initialization needs network access for pose weights.
- The web listener binds loopback. Secure cookies are disabled for this local
  HTTP profile only. .dockerignore excludes private runtime artifacts and caches.

## Public release work

Choose a CPU-capable host and spending/storage budget, build and test containers,
lock actual dependency versions and model-cache initialization, configure TLS,
set ICARE_COOKIE_SECURE=1, and preserve the public Host/protocol at every proxy.
The API trusts forwarded protocol headers in this container profile because it
is private behind nginx; never expose that API directly to untrusted clients.

Validate two visitors, upload/report isolation, admission/storage limits, expiry,
timeouts, model failures, readiness, restart and rollback through the actual
HTTPS URL. Verify example redistribution rights and controlled performance
measurements before publishing. Visitor/network admission and job-file storage budgets now exist. Tune these
against the actual host. The isolated model process supports hard cancellation.

Record actual costs, release commit/model/configuration, URLs and procedures in
the runbook. Pass the [release criteria](../docs/product/release_criteria.md).
