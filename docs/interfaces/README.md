# Version 1 integration defaults

Use these v1 contracts as the initial integration baseline. They are specifications,
not implemented endpoints. Teammates can start independently against them rather
than asking five AIs to negotiate five different architectures.

| Boundary | Owners | Reference |
| --- | --- | --- |
| Engine lifecycle/input/output | Persons 1 and 2, measurements reviewed by 4 | [Inference v1](inference.md) |
| HTTP jobs/media/incidents | Persons 2 and 3, access/limits reviewed by 5 | [API v1](api.md) |
| Units/provenance/missing values | Person 4 with Persons 1 and 2 | [Metrics](metrics.md) |
| Frameworks/storage/hosting topology | Person 5 with affected owners | [Stack](../project/stack.md) |

Person 5 records a necessary deviation in one linked issue/PR and updates consumers.
Do not silently rename fields, routes, states, timestamp units, coordinate systems,
or chosen framework. Fixtures/adapters must use the same contract and be labelled.

Frozen first-slice choices: CPU offline inference, FastAPI /api/v1, React/TypeScript/
Vite, original video plus timed source-coordinate poses, browser-session ownership,
SQLite metadata, per-job files, single-host same-origin deployment, and one active
inference job initially. Concurrency/limits change only with measured evidence.

No implementation or live URL is implied. Person 4 supplies actual example assets;
Person 5 records the real model/configuration/commit at release.
