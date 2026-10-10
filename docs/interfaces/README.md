# Version 1 integration defaults

Use these v1 contracts for the implemented engine/API/frontend integration.
Read [implementation status](../project/implementation_status.md) for evidence
and remaining optional features. Preserve the shared fields when extending it.

| Boundary | Responsibility | Reference |
| --- | --- | --- |
| Engine lifecycle/input/output | Development, measurements reviewed by 4 | [Inference v1](inference.md) |
| HTTP jobs/media/incidents | Development, access/limits reviewed by 5 | [API v1](api.md) |
| Units/provenance/missing values | Development | [Metrics](metrics.md) |
| Frameworks/storage/hosting topology | Deployment owner (Person 5) with affected owners | [Stack](../project/stack.md) |

Deployment owner (Person 5) records a necessary deviation in one linked issue/PR and updates consumers.
Do not silently rename fields, routes, states, timestamp units, coordinate systems,
or chosen framework. Fixtures/adapters must use the same contract and be labelled.

Frozen first-slice choices: CPU offline inference, FastAPI /api/v1, React/TypeScript/
Vite, original video plus timed source-coordinate poses, browser-session ownership,
SQLite metadata, per-job files, single-host same-origin deployment, and one active
inference job initially. Concurrency/limits change only with measured evidence.

No live URL is implied. Development verifies example assets and provenance;
Deployment owner (Person 5) records the real model/configuration/commit at release.
