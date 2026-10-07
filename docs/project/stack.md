# Default implementation stack

Use this baseline so five independent AI coding sessions produce compatible
components. This is a design decision, not an installed application. A justified
change is coordinated by Person 5 and affected owners in one documented PR.

| Boundary | Default | Owner |
| --- | --- | --- |
| Engine | Python 3.11, ONNX Runtime CPU, existing pose/heatmap operations | Person 1 |
| API | FastAPI with typed request/response validation | Person 2 |
| Jobs | Bounded worker execution, initially one concurrent inference job | Persons 2 and 5 |
| Metadata and files | SQLite job/session metadata; per-job files in ignored artifacts/ | Person 2 |
| Frontend | React, TypeScript, Vite; one npm lockfile | Person 3 |
| Browser media | Original video plus synchronized source-frame pose/probability records | Persons 1 2 and 3 |
| Public routing | One HTTPS origin; API under /api/v1, frontend at / | Person 5 |
| Reproduction | Docker Compose after actual service startup exists | Person 5 |
| Deployment | One CPU-capable host initially; provider/cost ceiling chosen after measurement | Person 5 |

Persons 2/3 pin actual library/runtime versions when scaffolding. Use a supported
Node version satisfying the chosen Vite release (the current guide requires
20.19+ or 22.12+); do not assume an old machine's Node works.
See [Vite's guide](https://vite.dev/guide/).

Do not run heavy inference in the ASGI request handler or an unbounded task queue.
Person 2 implements bounded execution, cancellation, and ownership; Person 1
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
Persons 1/5 verify and lock one workable runtime setup before packaging; do not
blindly install the test-only headless set into that same environment.

## Startup state

No web startup command exists after legacy UI removal. Current runnable checks
and audit tools remain documented. Persons 2/3 add actual service entry points;
Person 5 documents the verified combined startup. Do not advertise a Docker or
live URL before it works.
