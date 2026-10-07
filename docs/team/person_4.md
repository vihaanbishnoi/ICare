# Person 4 Evaluation benchmarks and research evidence

## Outcome and boundary

Own evaluation/, research/, examples/, evaluation commands in tools/,
icare_app/subject_audit.py, and dataset/evaluation docs. Provide approved clips,
real metrics, robustness evidence, and defensible contribution claims.

## First steps

1. Read [dataset access](../project/dataset.md) and [evaluation status](../project/evaluation_status.md).
2. Obtain publishable fall and normal clips with rights, labels, duration, and fall onset.
3. Audit existing metric evidence and record unavailable datasets/logs/subject IDs.
4. Agree the [measurement protocol](../interfaces/metrics.md) with Persons 1 and 2.

Use the [Person 4 starter prompt](prompts/person_4.md) for AI work. Missing original
data is a recorded limitation, not permission to fabricate evidence.

## Reuse or rebuild

Keep useful audit/signal tools and metric definitions. Recreate deleted notebooks
only if actually needed. Missing IDs cannot become a subject-independent claim.

Build a clean benchmark harness if the prototype upload timing is unreliable.
Measure the ordinary baseline before an optimization. A CPU run has no measured
GPU result; mark GPU usage not applicable.

## Deliverables and acceptance

- Approved labelled examples and provenance for the public demo.
- Reproducible manifests/protocol, sanitized evidence, plots, and failure cases.
- Classification evidence plus actual FPS, alert latency median/p95, false alarms
  per camera-hour, CPU/RAM, and temporal model calls.
- Blur/occlusion/cropping/missing-joint and hard-negative evaluation.
- Dataset, five-page results/analysis, novelty-evidence, and limitations report text.

Done when published numbers trace to model/data/configuration and an exact
experiment. Historical results stay separate from live performance, and missing
annotations/identities remain explicit.

Later compare one optimization with Person 1 under matched conditions, reporting
recall/latency/compute tradeoffs. Review with Person 1; supply tables to Persons 3 and 5.
