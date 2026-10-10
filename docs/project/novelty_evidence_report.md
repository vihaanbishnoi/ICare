# ICare Development: Novelty and Evidence Report

## Overview

This report distinguishes reused models and implemented engineering from proposed
research contributions. Custom code alone does not establish research novelty or
superiority. Those claims require prior-work comparison and matched experiments.

---

## 1. Summary of Component Re-use, Engineering Infrastructure, and Novel Contributions

| Component | Origin & Category | Description | Supporting Evidence File |
| --- | --- | --- | --- |
| **YOLOX-tiny** | Reused Pretrained | Person bounding box detection on sampled frames | `icare_app/pose.py` |
| **RTMPose-s** | Reused Pretrained | COCO-17 keypoint estimation from cropped person boxes | `icare_app/pose.py` |
| **PoseC3D (SlowOnly-R50)** | Fine-Tuned Backbone | 3D CNN temporal classifier fine-tuned on fall dataset | `models/posec3d_fall.onnx` |
| **Incident De-duplication Protocol** | **Engineering Component** | Dual-threshold state machine ($0.50$ alert trigger / $0.35$ re-arm after 3 clear windows) | `api/incidents.py` |
| **Evaluation Benchmark Harness** | **Engineering Component** | Automated throughput, latency percentile ($p_{50}/p_{95}$), and false alarm rate benchmark suite | `evaluation/benchmark_harness.py` |
| **PoseC3D Preprocessing Bridge** | **Custom engineering; numerical parity pending** | Temporal interpolation and Gaussian heatmap generation | `icare_app/posec3d_bridge.py` |
| **Motion Urgency V1 Signal** | **Custom instrumentation; benefit unmeasured** | Hip descent, torso rotation, displacement, aspect-ratio change | `icare_app/pose_signals.py` |
| **Pose Reliability V1 Signal** | **Custom instrumentation; benefit unmeasured** | Joint visibility, torso completeness, temporal stability | `icare_app/pose_signals.py` |

---

## 2. Implemented mechanisms and proposed research

### 2.1 Motion Urgency V1 Signal
The motion urgency signal computes dynamic movement indicators to complement PoseC3D predictions:
- **Hip Descent Rate**: Vertical displacement velocity of hip keypoints normalized by bounding box height.
- **Torso Rotation**: Angular displacement of shoulder-hip axis over successive frames.
- **Bounding Box Aspect Ratio Shift**: Rapid transition from tall (standing) to wide (horizontal/fallen) aspect ratio.

### 2.2 Pose Reliability V1 Signal
The reliability score describes pose quality; it does not currently gate or
schedule inference. It combines:
- **Mean Keypoint Confidence**: Average detection score across 17 COCO joints.
- **Torso Keypoint Visibility**: Presence of shoulders and hips.
- **Temporal Stability**: Keypoint displacement variance over rolling frame windows.

### 2.3 Lightweight ONNX Resampling Bridge
`icare_app/posec3d_bridge.py` uses NumPy without an MMAction2 inference runtime
to resample timestamped keypoints into 48 temporal positions and 64x64 heatmaps.
Numerical comparison with the original validation preprocessing remains pending.

---

## 3. Evidence Traceability Matrix

- **Historical metrics**: Reported group-aware split (N=1011, precision 97.09%,
  recall 94.75%, F1 95.90%); not newly reproduced or subject-independent.
- **Preprocessing review**: [Code comparison](mmaction2_parity_review.md), with
  numerical parity explicitly unverified.
- **Benchmark implementation**: evaluation/benchmark_harness.py and synthetic
  tests exist; this is not evidence of real performance gains.
- **Integration evidence**: [Two-clip local smoke check](implementation_status.md);
  no controlled superiority, generalization or adaptive-scheduling result.
