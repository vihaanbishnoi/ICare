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
and suite runner in `evaluation/run_benchmarks.py`. It measures:

1. **Classification performance**: Precision, Recall, Fall F1, Balanced Accuracy.
2. **Alert latency**: Median and p95 latency relative to annotated fall-onset timestamps.
3. **Throughput & Resources**: Average processing FPS, temporal model calls/min, CPU/RAM usage.
4. **False Alarm Rate**: False positive events per camera-hour.
5. **Robustness**: Degradation under keypoint dropout, Gaussian coordinate noise, frame cropping, and hard negatives (`evaluation/robustness_eval.py`).

