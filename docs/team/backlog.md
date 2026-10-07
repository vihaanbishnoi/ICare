# Five-part starter backlog

Person 5 creates and tracks these issues. This file is planning, not evidence
that issues or assignments have been published. Roles remain numbered.

## Person 1 Inference engine

- [ ] P1A Verify model loading, class order, preprocessing, and missing-model errors.
- [ ] P1B Deliver deterministic offline processing with final-output completion.
- [ ] P1C Expose timestamps, probabilities, poses, and measured runtime fields.
- [ ] P1D Test independent consumers, reset, no person, and completion with Person 4.

Reuse model operations; do not turn the old Gradio callbacks into the engine.

## Person 2 API jobs and incidents

- [ ] P2A Build example catalogue, example/upload jobs, results, incidents, reports.
- [ ] P2B Isolate state/storage and implement cancellation, errors, and cleanup.
- [ ] P2C Preserve useful incident semantics in a documented lifecycle.
- [ ] P2D Enforce ownership/limits with Person 5 and test two visitors/same-name uploads.

Agree contracts with Persons 1 and 3 first. Published results use real inference.

## Person 3 Frontend

- [ ] P3A Build responsive home and fall/normal/upload actions without login.
- [ ] P3B Display video/pose, confidence timeline, state, and incident details.
- [ ] P3C Add loading/errors, measured metrics, and How it works.
- [ ] P3D Connect to staging/live API and remove development fixtures from evidence.

Start fresh in frontend/. Webcam comes after the main journey works.

## Person 4 Evaluation and evidence

- [ ] P4A Obtain publishable examples with rights, labels, and annotated onset.
- [ ] P4B Reproduce historical metrics where data permit; record evidence gaps.
- [ ] P4C Measure FPS, latency percentiles, false alarms/hour, CPU/RAM, and model calls.
- [ ] P4D Evaluate robustness and supply plots/failure cases/report sections.
- [ ] P4E Later compare one optimization with Person 1 under matched conditions.

Data/example preparation starts immediately. Runtime benchmarking uses the real
P1/P2 pipeline; synthetic previews and cached playback are not benchmarks.

## Person 5 Deployment integration and release

- [ ] P5A Record chosen roles, create the board/issues, arrange access, coordinate contracts.
- [ ] P5B Package actual runtime/API/frontend with Docker and reproducible startup.
- [ ] P5C Deploy HTTPS staging with readiness, limits, retention, secrets, and cost cap.
- [ ] P5D Validate the full flow, publish a live URL, and complete the runbook.
- [ ] P5E Integrate README, architecture explanations, demo recording, academic report.

Persons 1 through 4 fix and document their own components. Person 5 integrates;
the project owner is not a sixth contributor.

## Milestones

1. Agree interfaces and obtain approved assets; all parts start in parallel.
2. Run example -> inference -> API -> frontend -> staging with genuine outputs.
3. Complete upload privacy/limits, incident/report flow, and real measurements.
4. Pass [public release criteria](../product/release_criteria.md).
5. Add optional webcam and one measured optimization.
6. Extra behaviours only after the core product is reliable.
