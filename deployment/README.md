# Deployment security integration and release

Owner: Person 5, individual unassigned. This is a planning boundary, not an
existing deployed service. Read the [Person 5 brief](../docs/team/person_5.md),
[product scope](../docs/product/brief.md), and [release criteria](../docs/product/release_criteria.md).

Person 5 owns staging/live packaging, HTTPS, readiness, cost limits, CI integration,
recovery/rollback, and final documentation/report assembly. Persons 1 through 4
supply their components and validation; the project owner is not the coordinator.

## First deployment

Choose/document a host that can run actual temporal inference within its limits.
Agree API/frontend startup and origins, model/cache initialization, quotas,
storage, and cleanup. Add real Docker/configuration after these decisions; do not
advertise docker compose startup before it works.

The public example/upload flow requires no login. Coordinate browser/job ownership
with Person 2 to keep private uploads/reports isolated. Secrets stay in the host's
secret store. An anonymous public demo still needs execution and spending limits.

## Release

- [ ] Real example -> runtime -> API -> frontend flow works on staging.
- [ ] Upload completion, ownership, limits, and cleanup are verified.
- [ ] Actual latency/FPS/resource and false-alarm measurements are documented.
- [ ] HTTPS, readiness, restart, and rollback are tested.
- [ ] README/report/demo recording contain the actual product and truthful evidence.
- [ ] The [runbook](runbook.md) has verified commands, costs, URLs, and procedures.

Webcam is optional after the core release. The legacy launcher was removed;
no web startup exists until API/frontend are implemented. A placeholder host
or pipeline is not release acceptance. Use the [default stack](../docs/project/stack.md).
