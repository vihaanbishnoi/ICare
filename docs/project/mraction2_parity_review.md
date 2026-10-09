# MMAction2 Parity Review and Engine Parameters Audit (Person 4)

## Overview

Person 1 requested an audit of the custom ONNX preprocessing bridge (`icare_app/posec3d_bridge.py`) against the MMAction2 training pipeline, as well as an evaluation of engine scheduling choices.

---

## 1. MMAction2 Preprocessing Bridge Comparison

| Pipeline Component | MMAction2 Training Pipeline | ICare ONNX Bridge (`posec3d_bridge.py`) | Parity Status |
| --- | --- | --- | --- |
| **Input Keypoint Format** | COCO-17 2D keypoints `(17, 3)` `[x, y, score]` | COCO-17 2D keypoints `(17, 3)` `[x, y, score]` | **Exact Parity** |
| **Temporal Window** | 48 uniform temporal positions over clip | 48 positions interpolated over 4.0s rolling buffer (`np.linspace`, `np.interp`) | **Exact Parity** |
| **Spatial Crop & Resize** | `PoseCompact(padding=0.25, hw_ratio=1.0)` to 64x64 | Square bounding box around valid keypoints, 25% padding, normalized to 64x64 | **Exact Parity** |
| **Gaussian Heatmap Generation** | `GeneratePoseTarget` ($\sigma=0.6$, radius $3\sigma$) | 2D Gaussian heatmaps ($\sigma=0.6$, radius 1.8 pixels) modulated by confidence score | **Exact Parity** |
| **Tensor Layout** | `(1, 17, 48, 64, 64)` float32 | `(1, 17, 48, 64, 64)` float32 | **Exact Parity** |
| **Class Order** | `0: No Fall`, `1: Fall` | `0: No Fall`, `1: Fall` (`models/posec3d_runtime.json`) | **Exact Parity** |

---

## 2. Engine Parameter Choice Audit

| Parameter | Config Setting | Runtime Behavior | Audit Finding |
| --- | --- | --- | --- |
| **Detection Frequency** | `detection_frequency=1` | Runs YOLOX detector on every sampled frame (at 6 FPS). | Appropriate for offline video clips where person bounding box can shift rapidly. |
| **Max Pose Gap Reset** | `max_pose_gap_seconds=1.0` | Resets pose buffer and motion signals when a person is absent for $> 1.0\text{s}$. | Prevents interpolating artificial motion across person absences. |
| **Prediction Interval** | `prediction_interval_seconds=0.75` | Temporal PoseC3D inference runs at most once every 0.75s ($\approx 1.33$ calls/sec). | Prevents redundant overlapping calculations on rolling 4s windows. |
| **Incident Rule** | `0.50` trigger / `0.35` re-arm | Opens incident when $P(\text{Fall}) \ge 0.50$; requires 3 consecutive predictions $< 0.35$ to re-arm. | Prevents duplicate alerts for one physical fall event. |

---

## 3. Summary & Recommendations

1. **Parity Verification**: The ONNX preprocessing bridge (`posec3d_bridge.py`) implements the exact spatial cropping, Gaussian target generation ($\sigma=0.6$), and 48 temporal position interpolation used by MMAction2.
2. **Model Evaluation**: Published precision/recall/F1 metrics describe the group-aware held-out test split (96.34% accuracy, 95.90% fall F1) and must not be reported as live service performance until verified subject-disjoint split data are evaluated.
