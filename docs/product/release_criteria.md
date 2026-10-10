# First public release acceptance

Deployment owner (Person 5) coordinates; each part supplies evidence for its own work. Checkboxes
are completed by demonstrated deployed behavior, not by the existence of a folder.

## Visitor experience

- [ ] Public HTTPS URL works without login or local install.
- [ ] Approved fall/normal examples use genuine model results.
- [ ] A permitted short upload completes with a useful result.
- [ ] Video/pose, confidence, event state, and incident details agree.
- [ ] Small-screen layout and loading/no-person/error cases work.
- [ ] Cached results and planned features are labelled.

## Correctness and access

- [ ] Two visitors cannot reset/overwrite/fetch each other's results.
- [ ] Completion occurs only after final inference/results.
- [ ] Incident timestamps/confidence/status and reports reflect actual output.
- [ ] Upload size/duration/rate/concurrency limits and cleanup are enforced.
- [ ] Ownership protects private results; job IDs alone are not the design.

## Evidence

- [ ] Classification results identify split/model/configuration and evidence.
- [ ] Actual FPS, median/p95 alert latency, CPU/RAM, and model calls are measured.
- [ ] False alarms per camera-hour include duration and event annotations.
- [ ] Missing data are pending/not applicable, never fabricated.
- [ ] Any published subject-independent/optimization claims have supporting
      experiments; absent experiments remain unverified rather than blocking
      the honest core release with an invented claim.

## Engineering and handoff

- [ ] Clean clone follows tested startup/container instructions.
- [ ] Model readiness/failure is visible before work is accepted.
- [ ] CI covers critical inference/API/product integration.
- [ ] Restart/cleanup/cost limits/rollback are documented and tested.
- [ ] README links the actual live URL, examples, architecture, results, and limits.
- [ ] Deployment owner (Person 5) integrates the report and demo recording with team evidence.

Webcam, extra behaviours, and publishable novelty are later work. They do not
replace a missing essential item.
