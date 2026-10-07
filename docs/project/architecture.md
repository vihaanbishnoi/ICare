# Active baseline and target architecture

## Target product

frontend/ (Person 3) -> /api/v1 FastAPI jobs/incidents/results (Person 2)
-> deterministic CPU inference engine using retained model operations (Person 1).

evaluation/, research/, examples/ (Person 4) provide labels, genuine demo assets,
metrics, and robustness evidence. deployment/, configs/, CI (Person 5) provide
one-origin HTTPS, bounded execution, readiness, packaging, recovery, and integration.

See the [default stack](stack.md) and [v1 interfaces](../interfaces/README.md).
These target components are not implemented by preparation.

## What is active now

icare_app/ contains retained pose/ONNX/heatmap computation, urgency/reliability
signals, incident/report semantic references, and subject-audit logic.
models/ contains the trained ONNX artifact and runtime metadata.
tools/ and tests/ contain existing audit/experiment commands and synthetic checks.

The Gradio UI and root launcher were removed. There is no active browser app,
web startup, global webcam session, or upload callback loop. No new HTTP/React
code exists yet. The ignored local backup is not product source.

## Boundaries for implementation

- Person 1 maps pose coordinates to original source dimensions and provides
  deterministic processing, cancellation, final-output completion, and readiness.
- Person 2 injects the engine into isolated jobs and writes unique owned results;
  retained session/report helpers are semantics, not a ready public-service design.
- Person 3 synchronizes source-relative pose/probability records with browser playback.
- Person 4 defines independent labels and truthful benchmark evidence.
- Person 5 verifies same-origin cookies/URLs, capacity limits, and actual startup.

The old latest-frame worker remains useful reference for optional live streaming,
but it must not drive offline jobs. Imported library code must not cause eager
model downloads merely by importing API request schemas.

## Contract changes

v1 defaults are ready to use for parallel implementation. Persons 1/2 own engine
changes; Persons 2/3 own API/media changes; Person 4 owns evidence meaning.
Person 5 coordinates a justified stack/contract change and updates consumers
in a documented integration PR rather than allowing incompatible AI-generated forks.
