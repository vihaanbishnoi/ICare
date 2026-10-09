# ICare Person 4: Novelty and Evidence Report

## Overview

This report documents the architectural innovations, original contributions, reused components, and supporting evidence for the ICare Pose-Based Fall Detection system.

---

## 1. Summary of Component Re-use, Engineering Infrastructure, and Novel Contributions

| Component | Origin & Category | Description | Supporting Evidence File |
| --- | --- | --- | --- |
| **YOLOX-tiny** | Reused Pretrained | Person bounding box detection on sampled frames | `icare_app/pose.py` |
| **RTMPose-s** | Reused Pretrained | COCO-17 keypoint estimation from cropped person boxes | `icare_app/pose.py` |
| **PoseC3D (SlowOnly-R50)** | Fine-Tuned Backbone | 3D CNN temporal classifier fine-tuned on fall dataset | `models/posec3d_fall.onnx` |
| **Incident De-duplication Protocol** | **Engineering Component** | Dual-threshold state machine ($0.50$ alert trigger / $0.35$ re-arm after 3 clear windows) | `api/incidents.py` |
| **Evaluation Benchmark Harness** | **Engineering Component** | Automated throughput, latency percentile ($p_{50}/p_{95}$), and false alarm rate benchmark suite | `evaluation/benchmark_harness.py` |
| **PoseC3D Preprocessing Bridge** | **Novel Custom Component** | Real-time temporal interpolation (48 positions over 4.0s) & $17\times 48\times 64\times 64$ Gaussian target generation | `icare_app/posec3d_bridge.py` |
| **Motion Urgency V1 Signal** | **Novel Custom Component** | Normalized hip descent rate, torso rotation, joint displacement, and aspect ratio change | `icare_app/pose_signals.py` |
| **Pose Reliability V1 Signal** | **Novel Custom Component** | Multi-factor confidence score combining joint visibility, torso completeness, and temporal stability | `icare_app/pose_signals.py` |

---

## 2. Detailed Technical Novelty Claims

### 2.1 Motion Urgency V1 Signal
The motion urgency signal computes dynamic movement indicators to complement PoseC3D predictions:
- **Hip Descent Rate**: Vertical displacement velocity of hip keypoints normalized by bounding box height.
- **Torso Rotation**: Angular displacement of shoulder-hip axis over successive frames.
- **Bounding Box Aspect Ratio Shift**: Rapid transition from tall (standing) to wide (horizontal/fallen) aspect ratio.

### 2.2 Pose Reliability V1 Signal
To prevent invalid inference when keypoint detection fails (e.g. extreme occlusion or partial frame containment), the reliability score combines:
- **Mean Keypoint Confidence**: Average detection score across 17 COCO joints.
- **Torso Keypoint Visibility**: Presence of shoulders and hips.
- **Temporal Stability**: Keypoint displacement variance over rolling frame windows.

### 2.3 Lightweight ONNX Resampling Bridge
Instead of executing full MMAction2 video loading pipelines at inference time, `icare_app/posec3d_bridge.py` implements a zero-dependency NumPy pipeline that interpolates timestamped keypoints directly into $64\times 64$ spatial heatmaps over 48 temporal slices.

---

## 3. Evidence Traceability Matrix

- **Accuracy & F1 Evidence**: Verified against held-out group-aware split ($N=1011$, Precision 97.09%, Recall 94.75%, F1 95.90%).
- **Parity Audit Evidence**: Verified in `docs/project/mmaction2_parity_review.md`.
- **Benchmark Code Evidence**: Verified in `evaluation/benchmark_harness.py` and `tests/test_evaluation_harness.py`.
