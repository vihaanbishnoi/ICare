# Person 5 Deployment security integration and release

## Outcome and boundary

Own deployment/, configs/, GitHub workflows, dependency reconciliation, board,
release docs, and final README/report integration. Coordinate the five parts;
do not transfer integration or publication to the project owner.

## First steps

1. Record chosen parts, arrange repository/host access, create [backlog](backlog.md) issues.
2. Coordinate [interface agreement](../interfaces/README.md) without writing everyone else's code.
3. Choose a low-cost staging approach and record its spending/capacity limits.
4. Package the actual runtime/API/frontend as they arrive and maintain a staging slice.

Use the [Person 5 starter prompt](prompts/person_5.md) and
[default stack](../project/stack.md). Publish the handoff baseline first; the
existing remote does not automatically contain this local preparation.

## Reuse or rebuild

Keep useful CI and ignore rules; expand checks for the new product. Resolve
duplicate OpenCV packages with Person 1 and verify a clean install.
Write Docker/configuration only against actual agreed startup paths.

Coordinate public-demo security with Person 2: HTTPS, ownership, upload/execution
limits, concurrency, retention, cleanup, safe errors, and secrets. Do not add
account login to the example/upload journey.

## Deliverables and acceptance

- Role selection, board/review rules, integration schedule.
- Reproducible startup/container, model/cache readiness, environment docs.
- HTTPS staging/live URL, monitoring, recovery, cleanup, and rollback.
- A deployment explanation covering actual hardware, cold starts, cost limits,
  and the tradeoffs between local/edge inference and the hosted demo.
- Tested [runbook](../../deployment/runbook.md) and release evidence.
- Final README, simple/deep architecture views, demo recording, and academic report
  assembled from the other parts' verified content.

Done when a recruiter can use the public URL and a clean clone can start the
product. Actual inference powers examples/uploads; private uploads/results remain
isolated; latency/capacity/cost limits are recorded; restart/rollback work.

Persons 1 through 4 fix their components and provide report sections. Account
holders may need to grant permissions or approve spending; this is not another
implementation role.
