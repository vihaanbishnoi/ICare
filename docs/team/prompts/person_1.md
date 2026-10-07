# Person 1 copyable starter prompt

I chose Person 1 for ICare. Read AGENTS.md, docs/team/person_1.md,
docs/project/stack.md, and docs/interfaces/inference.md. Inspect relevant engine
source and model metadata. If you cannot see these files, identify the missing
context before writing code; do not claim that local paths were read.

Implement the first standalone engine deliverable from P1A/P1B: load and verify
the existing CPU ONNX model and provide deterministic offline video processing
that drains final inference before completion. Reuse useful pose/heatmap operations,
not the removed Gradio app or its globals. Keep model/class/preprocessing meaning
unless validation supports a coordinated change.

Use the v1 engine boundary so Person 2 can inject this implementation into jobs.
Work only in Person 1's boundary and relevant engine tests/docs. Do not build
HTTP routes, frontend, deployment, retraining, or an adaptive scheduler.

Run meaningful completion/reset/no-person checks plus affected existing checks.
If a real clip or runtime resource is missing, state the limit without creating
fake measured confidence or accuracy. Finish with changed files, actual test
outcomes, and what Person 2/4 needs to integrate.
