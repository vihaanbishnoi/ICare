# Deployment and release

Deployment owner (Person 5) owns integration, hosting, HTTPS, cost limits, recovery and release
documentation. See the [current status](../docs/project/implementation_status.md)
and [runbook](runbook.md). There is no verified public deployment yet.

## Local packaging

With a running Docker daemon, from the repository root:

```sh
docker compose up --build -d --wait
# local diagnostics only: also expose the two unverified example clips
ICARE_ALLOW_UNVERIFIED_EXAMPLES=1 docker compose up --build -d --wait
deployment/smoke_test.sh            # needs the examples flag above
```

Open http://127.0.0.1:7860. Verified on 10 October 2026 (Colima, 4 CPU / 6 GB):
clean build, both examples and an upload through nginx, owner isolation (404),
range media, CSV/JSON reports, cross-origin 403, 413 above 50 MB, cancellation
followed by model reload, API restart with results preserved, and phone width.
CI repeats the build and `smoke_test.sh` on every pull request.

- Dockerfile.api installs the pinned runtime in requirements-runtime.txt with a
  single OpenCV (headless); rtmlib is installed `--no-deps` (rtmlib.txt) so its
  metadata cannot add opencv-python/opencv-contrib-python beside it.
- `PRELOAD_MODELS=1` (default, `ICARE_PRELOAD_MODELS`) downloads the YOLOX/RTMPose
  weights and loads the whole engine at build time, so the image starts ready
  without network access and a broken model fails the build. Image about 760 MB.
- The API runs as an unprivileged user with one uvicorn process; port 8000 is
  internal to Compose. The api-data volume holds SQLite and private job files.
- Dockerfile.web runs the frontend tests, builds React and serves dist via nginx.
- nginx preserves Host, overwrites X-Forwarded-For with the real peer (the API
  uses it for per-network admission, so client values must not pass through),
  serves /assets/ as immutable and index.html as no-cache.
- API resources default to two CPUs / 2 GB; observed RSS after jobs was about
  390-460 MB. These are initial limits, not measured capacity.
- The web listener binds loopback. Secure cookies are disabled for this local
  HTTP profile only. .dockerignore excludes private runtime artifacts and caches.

## Public release work

Choose a CPU-capable host and spending/storage budget, build and test containers,
lock actual dependency versions and model-cache initialization, configure TLS,
set ICARE_COOKIE_SECURE=1, and preserve the public Host/protocol at every proxy.
The API trusts forwarded headers in this container profile because it is private
behind nginx; never expose that API directly to untrusted clients. If another
TLS proxy sits in front of nginx, configure nginx `set_real_ip_from` /
`real_ip_header` for that proxy only, or every visitor shares one admission key.

Validate two visitors, upload/report isolation, admission/storage limits, expiry,
timeouts, model failures, readiness, restart and rollback through the actual
HTTPS URL. Verify example redistribution rights and controlled performance
measurements before publishing. Visitor/network admission and job-file storage budgets now exist. Tune these
against the actual host. The isolated model process supports hard cancellation.

Record actual costs, release commit/model/configuration, URLs and procedures in
the runbook. Pass the [release criteria](../docs/product/release_criteria.md).
