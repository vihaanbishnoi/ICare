# ICare repository instructions

## Responsibility

Development (the project owner and coding assistant) owns engine, API, frontend,
evaluation, tests and supporting documentation. Person 5 owns deployment:
hosting, HTTPS, operational budgets, container verification, recovery and live
release. The former five-person role briefs/handoffs are retired. Do not recreate
them or require cross-person approval to complete development work.

## Current product

Build a public no-login fall/normal-example and short-upload research demo.
CPU ONNX inference, FastAPI and React/Vite exist. Read docs/development.md and
docs/project/implementation_status.md for evidence and remaining inputs.
Keep the retired Gradio UI/app.py removed; do not use legacy global sessions as
product orchestration. AI assists coding; do not add LLM calls to fall inference.

## Implementation

Use docs/project/stack.md and v1 contracts in docs/interfaces/. Update affected
consumers together when a shared contract changes. Preserve useful computations
and trained weights; model/class/preprocessing/threshold changes require measured
evidence. Keep unrelated uncommitted work intact and avoid competing implementations.

## Verification

Run python -m tools.check_repository and python -m unittest discover -s tests -v.
Run frontend npm test, npm run build and npm run lint when affected. Add meaningful
failure/lifecycle/security/interaction tests. Record checks actually run.
requirements-test.txt is a separate test-only environment; the product uses root
requirements.txt plus api/requirements.txt and the frontend lockfile.

Historical metrics are group-aware, not verified subject-independent. Real model
outputs are required for inference evidence. Unknown data/latency/resource metrics
remain unknown; fixtures are labelled and never presented as published inference.
Do not invent video permissions, dataset identity, parity, accuracy or novelty.

## Hygiene

Keep credentials, raw private data, caches and generated reports out of Git.
Ignored artifacts/ may hold local legacy backups; do not restore them into source.
No mandatory webcam, added behaviours, training rewrite, Kubernetes or distributed
queue for the first example/upload release. Report changes, tests, limitations and
any deployment dependency. The completed academic report is an explicitly requested versioned deliverable;
its retained skeleton stays unchanged. Keep raw diagnostic outputs in artifacts/.
