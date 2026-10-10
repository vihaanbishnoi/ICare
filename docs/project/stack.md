# Default implementation stack

Use this baseline so five independent AI coding sessions produce compatible
components. This stack is now implemented locally. A justified
change is coordinated by Deployment owner (Person 5) and affected owners in one documented PR.

| Boundary | Default | Owner |
| --- | --- | --- |
| Engine | Python 3.11, ONNX Runtime CPU, existing pose/heatmap operations | Development |
| API | FastAPI with typed request/response validation | Development |
| Jobs | Bounded worker execution, initially one concurrent inference job | Development and 5 |
| Metadata and files | SQLite job/session metadata; per-job files in ignored artifacts/ | Development |
| Frontend | React, TypeScript, Vite; one npm lockfile | Development |
| Browser media | Original video plus synchronized source-frame pose/probability records | Development 2 and 3 |
| Public routing | One HTTPS origin; API under /api/v1, frontend at / | Deployment owner (Person 5) |
| Reproduction | Docker Compose packaging; build/runtime verification pending | Deployment owner (Person 5) |
| Deployment | One CPU-capable host initially; provider/cost ceiling chosen after measurement | Deployment owner (Person 5) |

The frontend lockfile records actual package versions. Use Node 24 or newer;
the regression runner uses built-in TypeScript stripping. Python runtime
requirements currently use version ranges; lock a tested deployment environment.
See [Vite's guide](https://vite.dev/guide/).

Do not run heavy inference in the ASGI request handler or an unbounded task queue.
Development implements bounded execution, cancellation, and ownership; Development
provides deterministic offline completion. A distributed queue is not a default
requirement. [FastAPI background-task guidance](https://fastapi.tiangolo.com/tutorial/background-tasks/)
distinguishes heavy computation from small background work.

Public examples may use labelled genuine cached analysis; uploaded clips use
actual inference. Store private files behind owned API access, not frontend public
assets. The anonymous ownership model is in the API contract.

## Deliberately excluded

No Gradio/FastRTC frontend, Next.js server duplicating Python API routes, account
login gate, paid LLM inference, Kubernetes, microservice split, or Redis/Celery
requirement for the first slice. Webcam and additional behaviours are later work.

## Existing dependency caveat

Installed RTMLib metadata lists both opencv-python and opencv-contrib-python.
Deleting one root requirement alone does not resolve this upstream dependency.
Development/5 verify and lock one workable runtime setup before packaging; do not
blindly install the test-only headless set into that same environment.

## Startup state

Run `python -m uvicorn api.main:create_app --factory --port 8000` from the root,
then `npm ci` / `npm run dev` in frontend/. Real CPU and browser checks passed
locally. Dockerfiles and Compose exist, but only configuration was validated;
public HTTPS and clean-container startup remain Deployment owner (Person 5)'s next delivery.
See [status](implementation_status.md) and [runbook](../../deployment/runbook.md).
