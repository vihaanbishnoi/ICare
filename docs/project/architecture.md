# Active baseline and target architecture

## Target product

frontend/ (Development) -> /api/v1 FastAPI jobs/incidents/results (Development)
-> deterministic CPU inference engine using retained model operations (Development).

evaluation/, research/, examples/ (Development) provide labels, genuine demo assets,
metrics, and robustness evidence. deployment/, configs/, CI (Deployment owner (Person 5)) provide
one-origin HTTPS, bounded execution, readiness, packaging, recovery, and integration.

See the [default stack](stack.md) and [v1 interfaces](../interfaces/README.md).
Engine, API and browser components are implemented and smoke-tested locally.
See [implementation status](implementation_status.md); public hosting remains pending.

## What is active now

icare_app/ contains retained pose/ONNX/heatmap computation, urgency/reliability
signals, incident/report semantic references, and subject-audit logic.
models/ contains the trained ONNX artifact and runtime metadata.
tools/ and tests/ contain existing audit/experiment commands and synthetic checks.

The Gradio UI and root launcher remain removed. The active application is
React/Vite -> same-origin FastAPI -> one CPU worker -> per-clip engine. SQLite
stores isolated metadata and random per-job folders hold private files. Public
examples are catalog-scoped. Timed records drive browser playback. nginx and
Compose provide local packaging, pending actual container verification. The
ignored legacy backup is not product source.

## Boundaries for implementation

- Development maps pose coordinates to original source dimensions and provides
  deterministic processing, cancellation, final-output completion, and readiness.
- Development injects the engine into isolated jobs and writes unique owned results;
  retained session/report helpers are semantics, not a ready public-service design.
- Development synchronizes source-relative pose/probability records with browser playback.
- Development defines independent labels and truthful benchmark evidence.
- Deployment owner (Person 5) verifies same-origin cookies/URLs, capacity limits, and actual startup.

The old latest-frame worker remains useful reference for optional live streaming,
but it must not drive offline jobs. Imported library code must not cause eager
model downloads merely by importing API request schemas.

## Contract changes

v1 defaults are ready to use for parallel implementation. Development own engine
changes; Development own API/media changes; Development owns evidence meaning.
Deployment owner (Person 5) coordinates a justified stack/contract change and updates consumers
in a documented integration PR rather than allowing incompatible AI-generated forks.
