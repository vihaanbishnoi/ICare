# Evaluation and benchmarks

Owner: Person 4. This folder provides repeatable evaluation and benchmark harnesses,
robustness evaluation protocols, and metric calculation suites in accordance with
[docs/interfaces/metrics.md](../docs/interfaces/metrics.md).

Read the [Person 4 brief](../docs/team/person_4.md) and
[evaluation status](../docs/project/evaluation_status.md).

## Running Benchmarks

Run the complete evaluation suite against approved clip manifests:

```powershell
python -m evaluation.run_benchmarks --manifest examples/manifest.json --output artifacts/evaluation/benchmark_report.json
```

## Key Components

- `evaluation/benchmark_harness.py`: Core benchmark harness measuring throughput (FPS), alert latency percentiles (median/p95), false alarm rates per camera-hour, resource utilization (CPU/RAM), and classification metrics (precision, recall, F1, balanced accuracy).
- `evaluation/robustness_eval.py`: Evaluates pipeline performance under synthetic keypoint dropout, noise, frame cropping, and hard negatives.
- `evaluation/run_benchmarks.py`: Executable runner producing versioned JSON metric reports into `artifacts/evaluation/`.
- `examples/manifest.json`: Approved demonstration asset annotations with fall onset timestamps and provenance metadata.

