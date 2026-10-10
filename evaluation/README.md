# Evaluation and benchmarks

Development owns evaluation code and scientific evidence. The owner identifies
[Kaggle Fall Video Dataset](https://www.kaggle.com/datasets/payutch/fall-video-dataset)
as the training source. Read [dataset evidence](../docs/project/dataset.md),
[metrics](../docs/interfaces/metrics.md) and the [report](../docs/project/ICare_Report.docx).

Run verified media with python -m evaluation.run_benchmarks --catalog
examples/manifest.json --output artifacts/evaluation/benchmark_report.json.
Existing clips are unverified; default execution reports missing approved media.
For local diagnostics only, add --allow-unverified. Pending labels do not produce
accuracy or event-delay claims. Failures are counted separately from predictions.

The harness records throughput, model calls and resource use; false-alarm rate
uses verified normal exposure. The report documents actual isolated API executions,
not a newly reproduced held-out dataset result. Historical reproduction still
requires original split/prediction files. Robustness perturbation code exists,
but broad video robustness/generalization experiments remain pending data.

The Gaussian audit tool compares the actual deployed heatmap function's stencil
at identical transformed coordinates against the reviewed MMAction2 v1.2.0
GeneratePoseTarget kernel. Supply the upstream source and SHA256 explicitly:
python -m tools.audit_heatmap_kernel --upstream-source artifacts/mmaction_pose_transforms.py
--expected-sha256 0fcaeb0a3a199216b2ea8a14a4f50e092ddffcaa346712724d678546d3c6c344
This is a diagnostic kernel comparison, not full preprocessing or model parity.
