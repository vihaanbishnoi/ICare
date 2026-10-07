# ICare repository instructions

## Goal and current state

Build a public no-login fall/normal-example and short-upload research demo.
The five parts are in docs/team/ownership.md; usernames are intentionally unassigned.
Person 5 coordinates integration and deployment; the project owner is not a sixth
developer. AI tools assist development; do not add LLM calls to fall inference.

The model/library baseline exists. The API/frontend are not implemented. The old
Gradio UI and app.py were removed intentionally. Do not recreate them, import
icare_app.ui, or turn legacy global sessions into the product architecture.
Retain trained ONNX weights and useful validated model operations.

## Starting a coding task

Read your numbered brief and relevant interface document. Use the default stack
in docs/project/stack.md and v1 contracts in docs/interfaces/. Do not independently
change framework, routes, field names, units, or model/class/preprocessing order.
Coordinate a necessary shared change through Person 5 and affected parts.

For setup/documentation tasks a chosen numbered part is not required. Follow the
current human task scope; a structure-only task does not implement product features.

## Ownership and scope

- Person 1: pose/ONNX/heatmap engine, model configuration, lifecycle tests.
- Person 2: api/, isolated jobs, incident/report adaptation, API tests.
- Person 3: frontend/, browser experience and interaction tests.
- Person 4: evaluation/, research/, examples/, evaluation tools and evidence.
- Person 5: deployment/, configs/, CI/dependencies, integration and release docs.

Implement one backlog deliverable per PR. Leave other people's work intact.
Do not build all five parts in one task, overwrite unrelated uncommitted changes,
or generate parallel competing implementations. Use the role's starter prompt
under docs/team/prompts/ and record decisions and handoff evidence in the PR.

## Evidence and verification

Existing commands from repository root:

- python -m tools.check_repository
- python -m unittest discover -s tests -v

requirements-test.txt is for a separate test-only environment. requirements.txt
contains the retained model/evaluation dependencies, not a complete product stack.
Add meaningful component tests as features are implemented; run affected checks.
Do not claim real-model/browser/deployment checks that were not run.

Historical metrics are group-aware, not confirmed subject-independent. Unknown
latency, missing data, and unused GPU metrics remain unknown/not applicable.
Use actual ONNX outputs for published confidence/incident evidence. Development
fixtures must be labelled and excluded from the published inference path.

## Repository hygiene

No credentials, raw private data, local model caches, or generated reports in Git.
Ignored artifacts/ may contain a local legacy backup; it is not product source.
Do not restore retired UI from it. No mandatory webcam, added behaviours, training
rewrite, Kubernetes, or distributed queue for the first example/upload release.
Report changed files, test outcomes, limitations, and the next integration dependency.
