# Evaluation status

## Subject-disjoint audit

The reported split is group-aware, but it is not currently verified as
subject-disjoint.

Evidence available in this repository:

- The historical training notebook requires label, normalized stem, CSV/video paths,
  exact-pose hash, group ID, and frame count.
- It does not require or construct a verified subject identifier. The notebooks
  have since been removed from the working tree; earlier commits retain them.
- The split metadata and original dataset are intentionally not stored in the
  repository, so identities cannot be reconstructed locally.

Therefore, the existing 96.34% accuracy and 95.90% fall F1 must continue to be
reported as group-aware held-out results, not subject-independent results.

When a split manifest with verified subject IDs is available, run:

```powershell
python -m tools.audit_subject_split fall_pose_split_metadata.csv `
  --subject-column subject_id `
  --output artifacts/evaluation/subject_split_audit.json
```

The audit requires at least 95% subject-ID coverage and reports every subject
that crosses train, validation, or test splits.

## Repeatable evaluation framework (Person 4)

Person 4 implemented the automated benchmark harness in `evaluation/benchmark_harness.py`
and suite runner in `evaluation/run_benchmarks.py`. It integrates directly with `icare_app.engine`:

1. **Classification performance**: Precision, Recall, Fall F1, Balanced Accuracy.
2. **Alert latency**: Median and p95 latency relative to annotated fall-onset timestamps (`timestamp_seconds`).
3. **Throughput & Resources**: Average processing FPS, temporal model calls/min, CPU/RAM usage (unmeasured values remain `None`).
4. **False Alarm Rate**: False positive incident events per camera-hour using `IncidentTracker` (`0.50` trigger, `0.35` re-arm).
5. **Robustness & Hard Negatives**: Degradation under keypoint dropout, Gaussian coordinate noise, frame cropping, and hard negatives (fast sitting, lying down, crouching) in `evaluation/robustness_eval.py`.
6. **Provenance & Catalog Parity**: Shared schema in `examples/catalog.json` with API Person 2; media provenance is explicitly marked `pending` until approved public assets are added.
7. **MMAction2 Parity Review**: See `docs/project/mraction2_parity_review.md` for the audit of ONNX preprocessing vs MMAction2 and engine parameters.


