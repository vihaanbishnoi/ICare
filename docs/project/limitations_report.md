# ICare Development: Limitations and Data Boundaries Report

## Overview

This report documents the evaluation limitations, dataset boundaries, hardware constraints, and domain gaps identified during Development's audit of the ICare system.

---

## 1. Dataset & Subject Identity Limitations

### 1.1 Unverified Subject-Disjoint Boundary
- **Current Finding**: The reported held-out test split ($N = 1011$) is group-aware (preventing duplicate pose sequences from crossing splits), but **subject identities were not recorded in the source dataset metadata**.
- **Impact**: The reported 96.34% accuracy and 95.90% F1 score must be cited strictly as **group-aware held-out performance**, not subject-independent generalizability.
- **Audit Tool**: `tools/audit_subject_split.py` enforces a 95% subject-ID coverage threshold and will audit subject-disjoint splits when subject metadata become available.

### 1.2 Demonstration Asset Provenance Status
- **Current Finding**: Public demonstration video clips in `examples/catalog.json` and `examples/manifest.json` have `provenance_status: "pending"`.
- **Impact**: Unverified mock predictions or synthetic clips must never be presented as real inference evidence. `evaluation/run_benchmarks.py` strictly refuses to generate fake metric reports when media files are unavailable.

---

## 2. Model & Pipeline Constraints

### 2.1 Single-Person Tracking Restriction
- **Current Finding**: The pose extraction pipeline (`icare_app/pose.py`) follows only the single largest detected person in the frame.
- **Impact**: In multi-person environments (e.g. crowded rooms or emergency responders entering the frame), secondary individuals are ignored, which may cause tracking resets if person bounding box priority shifts.

### 2.2 CPU vs GPU Hardware Execution Boundary
- **Current Finding**: The ONNX Runtime backend (`icare_app/onnx_backend.py`) uses the CPU execution provider (`device="cpu"`).
- **Impact**: Real processing throughput (FPS) and resource utilization will be measured when public video clips are processed through `icare_app.engine`. GPU utilization is explicitly recorded as **Not Applicable (N/A)**.

### 2.3 Live Domain & Camera Angle Gap
- **Current Finding**: Model training utilized fixed-camera indoor video datasets.
- **Impact**: Significant camera movement, low lighting, heavy motion blur, or steep top-down camera angles degrade keypoint estimation quality and lower Pose Reliability V1 scores.

---

## 3. Mandatory Reporting Safeguards

1. **No Metric Fabrication**: All benchmark metrics must trace directly to real engine executions (`icare_app.engine`) and verified ground-truth annotations.
2. **Clear Labeling of Test Fixtures**: Synthetic adapters used in unit testing (`tests/test_evaluation_harness.py`) must be labelled as test fixtures and excluded from published evidence.
