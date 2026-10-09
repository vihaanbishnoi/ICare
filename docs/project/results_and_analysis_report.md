# ICare Person 4: Results and Analysis Report

## Executive Summary

This report documents the baseline evaluation, metric calculations, operational throughput, alert latency definitions, and robustness protocols for the ICare Pose-Based Fall Detection system. ICare uses person detection (YOLOX-tiny), pose keypoint estimation (RTMPose-s COCO-17), and temporal action recognition (fine-tuned binary PoseC3D) to detect human falls from video sequences without relying on single-frame RGB classification.

---

## 1. Classification Metrics & Held-Out Test Evaluation

### 1.1 Test Set Performance Evidence

The binary PoseC3D temporal model was evaluated on a held-out group-aware test split ($N = 1,011$ samples). The decision threshold was set to $P(\text{Fall}) \ge 0.50$.

| Metric | Result Value | Definition & Traceability |
| --- | ---: | --- |
| **Fall Precision** | **97.09%** | $\text{TP} / (\text{TP} + \text{FP}) = 433 / 446$ |
| **Fall Recall** | **94.75%** | $\text{TP} / (\text{TP} + \text{FN}) = 433 / 457$ |
| **Fall F1 Score** | **95.90%** | $2 \times (\text{Precision} \times \text{Recall}) / (\text{Precision} + \text{Recall})$ |
| **Balanced Accuracy** | **96.20%** | $(\text{Sensitivity} + \text{Specificity}) / 2$ |
| **PR-AUC (Average Precision)** | **99.61%** | Area under the Precision-Recall curve |
| **Overall Accuracy** | **96.34%** | $(\text{TP} + \text{TN}) / N = 974 / 1011$ |

### 1.2 Confusion Matrix Breakdown

The evaluation yielded the following confusion counts:

```text
                     Predicted No Fall    Predicted Fall
True No Fall (TN/FP)        541                 13
True Fall    (FN/TP)         24                433
```

- **True Negatives ($\text{TN} = 541$)**: Correctly identified normal daily activities.
- **True Positives ($\text{TP} = 433$)**: Correctly identified physical fall events.
- **False Negatives ($\text{FN} = 24$)**: Missed fall events (primarily slow controlled descents onto furniture).
- **False Positives ($\text{FP} = 13$)**: Normal actions misclassified as falls (e.g., rapid crouching or collapse-like sitting).

---

## 2. Real-Time Operational Benchmarks & Measurement Protocol

### 2.1 Latency Definitions & Incident Tracker Rules

Per [`docs/interfaces/metrics.md`](../interfaces/metrics.md), event alert latency is defined strictly as:

$$\text{Alert Latency} = t_{\text{alert}} - t_{\text{fall\_onset}}$$

Where:
- $t_{\text{fall\_onset}}$ is the annotated ground-truth timestamp when the physical fall begins in the video timeline.
- $t_{\text{alert}}$ is the timestamp of the first model prediction reaching $P(\text{Fall}) \ge 0.50$.

### 2.2 Incident De-duplication Protocol

To prevent overlapping 4-second temporal windows from registering duplicate alerts for the same physical fall, the detector uses `IncidentTracker` (`api/incidents.py`):
1. **Trigger**: Opens an incident immediately when $P(\text{Fall}) \ge 0.50$.
2. **Re-arm**: Requires 3 consecutive temporal predictions below $P(\text{Fall}) < 0.35$ before re-arming the detector.

### 2.3 System Throughput & Hardware Measurement Protocol

Inference is performed strictly using ONNX Runtime with the CPU execution provider (`device="cpu"`). GPU utilization is recorded as **Not Applicable**.

| Metric | Protocol Specification / Limit | Operational Context & Measurement Status |
| --- | --- | --- |
| **Processing Throughput (FPS)** | **Pending real video execution** | 12.0 FPS was the legacy prototype camera capture rate. Real processing FPS will be measured when public video clips are processed through `icare_app.engine`. |
| **Temporal Model Call Rate** | **Configured upper bound ($\le 1.33$ calls/sec)** | Prediction interval is set to 0.75s (`prediction_interval_seconds = 0.75`). Actual call rate at 6 FPS sampling is $\approx 1$ call per 0.83s. |
| **Process CPU Utilization** | **Pending execution** (Process %) | Process-level CPU % measured via `psutil` during engine runs. Unmeasured values stay `None`. |
| **Process Peak RAM (RSS)** | **Pending execution** (Peak RSS MB) | Process resident set size measured via `psutil`. Unmeasured values stay `None`. |

---

## 3. Robustness Evaluation & Hard-Negative Activity Analysis

### 3.1 Perturbation Testing Framework

The robustness evaluator (`evaluation/robustness_eval.py`) tests pose degradation across synthetic coordinate noise, joint dropout, and border cropping:

1. **Keypoint Dropout**: Random zeroing of keypoint coordinates simulating self-occlusions and missing limb visibility.
2. **Gaussian Coordinate Noise**: Additive zero-mean Gaussian noise ($\sigma \in [1.0, 5.0]$ pixels) on joint $(x, y)$ positions.
3. **Frame Edge Cropping**: Clipping keypoints outside cropped image bounds.

### 3.2 Hard-Negative Activity Protocol

To prevent false alarms during routine movement, six specific hard-negative activity cases are evaluated with expected outcome `No Fall`:
1. **Fast Sitting**: Rapid sitting into a low chair.
2. **Normal Lying Down**: Controlled lying down on a couch or bed.
3. **Crouching**: Bending down to retrieve a dropped item.
4. **Tying Shoe**: Prolonged forward bending to tie footwear.
5. **Leaving Frame**: Rapid walking out of camera view.
6. **Camera Occlusion**: Partial obstruction of camera line-of-sight.

---

## 4. Evidence Integrity & Missing Data Boundaries

1. **Group-Aware vs. Subject-Disjoint**: The reported 96.34% accuracy describes the group-aware held-out test split. Because subject identifiers were unavailable in the historical dataset, this performance must not be claimed as subject-independent generalization.
2. **Media Asset Provenance**: Public demonstration media clips in `examples/catalog.json` are marked with `provenance_status: "pending"` until approved, rights-verified public video clips are procured.
