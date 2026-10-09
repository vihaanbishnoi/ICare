# Deployment security integration and release

Owner: Person 5, individual unassigned. This is a planning boundary, not an
existing deployed service. Read the [Person 5 brief](../docs/team/person_5.md),
[product scope](../docs/product/brief.md), and [release criteria](../docs/product/release_criteria.md).

Person 5 owns staging/live packaging, HTTPS, readiness, cost limits, CI integration,
recovery/rollback, and final documentation/report assembly. Persons 1 through 4
supply their components and validation; the project owner is not the coordinator.

## API + engine container

Packages Person 2's API and Person 1's engine; the frontend and HTTPS proxy are
added when they exist. From the repository root:

```bash
docker compose -f deployment/compose.yaml up --build -d
curl http://127.0.0.1:8000/api/v1/health   # {"status":"ok"}
curl http://127.0.0.1:8000/api/v1/ready    # 200 once the engine has loaded
docker compose -f deployment/compose.yaml down
```

| File | Purpose |
| --- | --- |
| `Dockerfile` | Python 3.11 slim, non-root `icare` user, one uvicorn worker, `/data` volume |
| `compose.yaml` | Single host; port bound to 127.0.0.1; limits come from `ICARE_*` variables |
| `requirements-runtime.txt` | Pinned runtime set with `opencv-python-headless` as the only OpenCV |
| `rtmlib.txt` | rtmlib, installed with `--no-deps` so it cannot add a second OpenCV |

**Model weights.** `models/posec3d_fall.onnx` is copied in. rtmlib downloads the
YOLOX-tiny and RTMPose-s weights (URLs in `icare_app/pose.py`) into
`$TORCH_HOME=/opt/icare/model-cache`. With the default `PRELOAD_MODELS=1` the
build downloads them and loads the whole engine once, so the image starts ready
offline and a broken model fails the build. `ICARE_PRELOAD_MODELS=0` skips that;
the container then needs network access to those URLs at startup, otherwise
`/ready` stays 503 `model_unavailable`.

**OpenCV.** rtmlib's metadata requires both `opencv-python` and
`opencv-contrib-python`; installed together they overwrite each other's `cv2`.
The engine and rtmlib's detector/pose path use only core OpenCV functions, so
the container installs headless OpenCV alone, and `pip check` reports the two
packages rtmlib declares as missing; that report is expected. The root
`requirements.txt` (development/evaluation) is unchanged.

**Data.** SQLite job metadata and per-job files live in the `icare-data` volume
and survive restarts. Retention/cleanup is the API's (24 h default).

**CI.** The `API container smoke test` job builds with `PRELOAD_MODELS=0`, then
checks `/health`, that `/ready` is 503 without pose weights, that `/examples` loads
the committed catalogue, a single OpenCV package, and that PoseC3D loads.

Still to decide before staging: host, cost cap, memory/CPU limits (after Person 4
measures them), public example video route (Person 2), the frontend container
(Person 3) and the HTTPS reverse proxy with same-origin `/` and `/api/v1`.

## First deployment

Choose/document a host that can run actual temporal inference within its limits.
Agree API/frontend startup and origins, model/cache initialization, quotas,
storage, and cleanup.

The public example/upload flow requires no login. Coordinate browser/job ownership
with Person 2 to keep private uploads/reports isolated. Secrets stay in the host's
secret store. An anonymous public demo still needs execution and spending limits.

## Release

- [ ] Real example -> runtime -> API -> frontend flow works on staging.
- [ ] Upload completion, ownership, limits, and cleanup are verified.
- [ ] Actual latency/FPS/resource and false-alarm measurements are documented.
- [ ] HTTPS, readiness, restart, and rollback are tested.
- [ ] README/report/demo recording contain the actual product and truthful evidence.
- [ ] The [runbook](runbook.md) has verified commands, costs, URLs, and procedures.

Webcam is optional after the core release. The legacy launcher was removed;
the API container above is the only web startup until the frontend exists. A placeholder host
or pipeline is not release acceptance. Use the [default stack](../docs/project/stack.md).
