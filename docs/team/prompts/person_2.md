# Person 2 copyable starter prompt

I chose Person 2 for ICare. Read AGENTS.md, docs/team/person_2.md,
docs/project/stack.md, docs/interfaces/api.md, and docs/interfaces/inference.md.
If repository files are unavailable, identify needed context before coding.

Implement P2A/P2B's first testable FastAPI slice in api/: /api/v1 example catalogue,
isolated job creation/status, typed v1 responses, and an injectable engine boundary.
Use explicit test adapters while Person 1's real engine is unavailable; readiness
and published results must not pretend that an adapter is real inference.

Start orchestration fresh. Reuse valid incident field/threshold semantics from
inference.py without restoring the removed UI, global sessions, frame-dropping
upload flow, or repeated report paths. Add SQLite ownership/state and bounded
execution according to the v1 defaults. Do not run heavy inference in the
request loop.

Keep work within Person 2 plus its tests/docs. Do not build frontend, alter model
preprocessing, pick a second framework, or deploy the entire product. Test two
visitors, job completion, error states, and unauthorized access. Finish with
actual tests, contract version, and the adapter/API handoff for Persons 1/3/5.
