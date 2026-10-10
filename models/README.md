# Model artifacts

Runtime owner: Development. Evaluation evidence: Development. Individuals unassigned.

The existing posec3d_fall.onnx and posec3d_runtime.json are retained. Metadata
describe two classes, No Fall and Fall, 17 joints, 48 temporal positions, and
64 by 64 heatmaps. Verify class order and preprocessing in an actual model run.

Before replacing an artifact, record its checksum, provenance, checkpoint,
configuration, validation results, and compatibility with engine/API consumers.
Do not imply a new artifact's historical metrics apply without evaluation.

Keep training checkpoints and raw datasets out of Git. Pose detector/estimator
downloads and cache/readiness behavior must be documented by Development and 5.
Unavailable training/provenance evidence stays explicit.
