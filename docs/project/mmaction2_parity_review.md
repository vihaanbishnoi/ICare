# MMAction2 Parity Review and Engine Parameters Audit (Development)

## Overview

Development requested a review of the custom ONNX preprocessing bridge (`icare_app/posec3d_bridge.py`) against the MMAction2 training pipeline, as well as an evaluation of engine scheduling choices.

---

## 1. MMAction2 Preprocessing Bridge Comparison

| Pipeline Component | MMAction2 Training Pipeline | ICare ONNX Bridge (`posec3d_bridge.py`) | Audit Finding & Verification Status |
| --- | --- | --- | --- |
| **Input Keypoint Format** | COCO-17 2D keypoints `(17, 3)` `[x, y, score]` | COCO-17 2D keypoints `(17, 3)` `[x, y, score]` | **Matches by code reading, not numerically verified** |
| **Temporal Window Sampling** | Samples 48 frames uniformly distributed **across the entire clip** | Uses a rolling **fixed 4-second window** over the latest poses (`PoseSequenceBuffer`) | **Structural Difference**: MMAction2 spans full clip duration; ICare uses rolling 4s window. |
| **Spatial Crop & Resize** | `PoseCompact(padding=0.25, hw_ratio=1.0)` to 64x64 | Square bounding box around valid keypoints, 25% padding, normalized to 64x64 | **Matches by code reading, not numerically verified** |
| **Gaussian Heatmap Generation** | `GeneratePoseTarget` ($\sigma=0.6$, radius $3\sigma$) | 2D Gaussian heatmaps ($\sigma=0.6$, radius 1.8 pixels) modulated by confidence score | **Matches by code reading, not numerically verified** |
| **Tensor Layout** | `(1, 17, 48, 64, 64)` float32 | `(1, 17, 48, 64, 64)` float32 | **Matches by code reading, not numerically verified** |
| **Class Order** | `0: No Fall`, `1: Fall` | `0: No Fall`, `1: Fall` (`models/posec3d_runtime.json`) | **Matches by code reading, not numerically verified** |

*Note: Numerical tensor parity requires running a sample through MMAction2 and the ONNX bridge simultaneously once MMAction2 dependencies are available.*

---

## 2. Engine Parameter Choice Audit

| Parameter | Config Setting | Runtime Behavior | Audit Finding |
| --- | --- | --- | --- |
| **Detection Frequency** | `detection_frequency=1` | Runs YOLOX detector on every sampled frame (at 6 FPS). | Appropriate for offline video clips where person bounding box can shift rapidly. |
| **Max Pose Gap Reset** | `max_pose_gap_seconds=1.0` | Resets pose buffer and motion signals when a person is absent for $> 1.0\text{s}$. | Prevents interpolating artificial motion across person absences. |
| **Prediction Interval** | `prediction_interval_seconds=0.75` | Temporal PoseC3D inference runs at most once every 0.75s ($\approx 1.33$ calls/sec limit). | Configured upper bound limit; actual processing rate depends on frame sampling rate (e.g. $\approx 1$ call every $0.83\text{s}$ at 6 FPS). |
| **Incident Rule** | `0.50` trigger / `0.35` re-arm | Opens incident when $P(\text{Fall}) \ge 0.50$; requires 3 consecutive predictions $< 0.35$ to re-arm. | Prevents duplicate alerts for one physical fall event. |

---

## 3. Summary & Recommendations

1. **Verification Status**: Code reading confirms that spatial crop, Gaussian target generation ($\sigma=0.6$), and tensor formatting match MMAction2 formulas. Full numerical verification requires running identical input tensors through both frameworks.
2. **Temporal Difference**: Note the structural difference between MMAction2 full-clip sampling and ICare's rolling 4-second window.
3. **Model Evaluation**: Published precision/recall/F1 metrics describe the group-aware held-out test split (96.34% accuracy, 95.90% fall F1) and must not be reported as live service performance until verified subject-disjoint split data are evaluated.

## Numerical kernel diagnostic on 10 October 2026

The actual deployed heatmap function and pinned MMAction2 v1.2.0 Gaussian
method were compared at identical transformed coordinates across four diagnostic
cases. Maximum absolute delta was 0.003454. Spatial/temporal transforms and
model predictions were not jointly compared. The Gaussian stencil discrepancy
and full-clip versus rolling-window difference prevent a full-parity claim.
Preprocessing and model weights were preserved pending paired validation data.
See tools/audit_heatmap_kernel.py and the completed report for scope and evidence.
