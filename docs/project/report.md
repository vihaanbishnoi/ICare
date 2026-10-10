# ICare Pose Based Fall Detection

Project report


<!-- page break -->

## 1 Abstract

ICare is a research prototype for detecting falls from sequences of human body poses and presenting the resulting evidence through a browser. The problem is to distinguish fall-like movement from ordinary activities while preserving the temporal information that a single frame cannot describe. The proposed pipeline combines YOLOX tiny person detection, RTMPose small estimation of 17 COCO joints, timestamped pose buffering, Gaussian heatmaps and a binary PoseC3D temporal classifier executed with ONNX Runtime on the CPU.

The project owner identifies the training source as the Fall Video Dataset distributed by payutch on Kaggle. Historical project records report 6,766 cleaned samples and a group-aware held-out test set of 1,011 samples. At a fall-probability threshold of 0.50, the reported fall precision is 97.09%, recall is 94.75%, F1 score is 95.90% and overall accuracy is 96.34%. These historical results were not reproduced from the original prediction files during the current verification and do not establish subject-independent generalization.

Local execution of two six-second diagnostic clips produced six temporal predictions and one incident for the fall clip, and four predictions with no incident for the normal clip. Analysis took 22.52 and 16.92 seconds respectively on the measured CPU environment. The implemented contribution is a traceable video-to-pose-to-incident workflow with private jobs, synchronized playback, bounded admission and recoverable model-process execution. Larger independently labelled evaluations, verified example provenance and public deployment remain necessary before operational reliability or superiority can be claimed.


<!-- page break -->

## 2 Introduction

### 2 1 Problem Statement

A fall-detection application must identify a meaningful movement event rather than react to an isolated appearance. Sitting quickly, bending forward, lying down and leaving the camera view can resemble parts of a fall. The position of a person in one image does not explain whether the body is descending abruptly, changing orientation or completing a controlled action. ICare addresses this problem by representing movement as a temporal sequence of joint positions and classifying that sequence.

The system accepts a prerecorded short video, samples frames, identifies the largest visible person and estimates a COCO-17 body pose for each usable sample. Successive poses are placed on a source-video timeline. A rolling sequence is transformed into heatmaps and supplied to the temporal classifier, which returns probabilities for No Fall and Fall. Incident logic records threshold crossings and prevents overlapping windows from repeatedly opening the same event.

### 2 2 Motivation and Intended Use

The prototype supports research review, demonstrations and controlled video analysis. A user can inspect a source video alongside pose estimates, confidence over time and incident records instead of receiving only an unexplained binary label. This makes errors easier to examine: a missed detection may involve missing poses, inadequate temporal coverage, an ambiguous action or a classifier response. Each explanation must be checked against the relevant recording and output rather than inferred from the final class alone.

The immediate product is a no-login example-and-upload experience with downloadable JSON and CSV evidence. Uploaded files and results belong to an anonymous browser session and are not exposed solely because someone knows a job identifier. The work combines model behavior with the practical requirements of a usable research interface, including readiness, validation, cancellation, resource limits and recovery. Webcam monitoring, caregiver notification, multiple-person tracking and emergency response are outside this release.


<!-- page break -->

## 2 Introduction

### 2 3 Objectives

The primary objective is to deliver a complete path from a permitted video to actual model predictions and inspectable incident evidence. The inference objective is deterministic source-time sampling, stable class interpretation and completion only after the final temporal window has been processed. The interface objective is to synchronize video, joint overlay, confidence chart and incident timing while representing absent or stale information as unavailable.

The service objective is to isolate visitors, validate uploaded content, bound accepted work and storage, support cancellation, and recover when a model call crashes or hangs. The evaluation objective is to separate historical sample-classification results from newly measured clip execution and to preserve the conditions under which every number was obtained. Unknown labels, event onset, permissions and generalization are explicitly excluded from unsupported performance claims.

### 2 4 Scope and Evaluation Questions

The current model follows the largest detected person. Frames are sampled at six per source second, with detection performed on every sampled frame. This sampling rate is a configured source-time cadence; it is not a claim that the CPU analyzes six frames each wall-clock second. A clip can therefore take longer than its playback duration to process. The application presents completed analysis rather than promising instantaneous monitoring.

The report asks four practical questions: whether actual pose and probability records complete through the API and browser; how confidence and instrumented motion signals change during the two available clips; what CPU, memory and processing cost were measured; and which observed implementation issues or missing evidence restrict interpretation. The short executions support integration and behavior analysis, but their size and unverified source annotations prevent estimation of population accuracy, false alarms per monitoring hour or reliable event-onset latency.

A scientific claim of superiority requires a specified comparison under matched data, preprocessing, thresholds and hardware. Integrating pretrained models into an application does not by itself establish a new model family or a research advantage. The report therefore describes implemented engineering contributions and the experiments needed to evaluate proposed improvements without reporting invented gains.


<!-- page break -->

## 3 Proposed Model Architecture

### 3 1 End to End Processing Pipeline

The pipeline converts decoded video frames into timestamped body-pose observations and then into temporal decisions. YOLOX tiny finds a person bounding box. RTMPose small estimates 17 joints with raw confidence scores. Coordinates are mapped back to the original source-video dimensions so browser overlays and recorded evidence use the same coordinate system.

Figure 1  Implemented video pose heatmap classifier and incident pipeline

The pose buffer retains up to four seconds of observations and requires at least six successful poses spanning two seconds before classification. Interpolation resamples available observations to 48 temporal positions. A missing-person gap longer than one second resets the track and its temporal state, preventing artificial movement across an absence. The last usable window is processed before the job is marked complete.

### 3 2 Pose Heatmaps and Feature Representation

Each resampled COCO joint produces a confidence-weighted Gaussian heatmap at 64 by 64 spatial resolution, with sigma 0.6. The ONNX input has dimensions batch by 17 joints by 48 temporal positions by 64 by 64 pixels. This representation expresses body geometry and movement over time. Raw RTMPose scores are retained as finite model outputs; they are not treated as calibrated fall probabilities and can exceed one. Fall probabilities remain constrained to the interval from zero to one.


<!-- page break -->

## 3 Proposed Model Architecture

### 3 3 Temporal Classifier and Training Configuration

PoseC3D uses the SlowOnly-R50 architecture configured for 17 heatmap input channels and a binary classification head. The retained training notebook fine-tunes an NTU60-pretrained checkpoint through MMAction2 v1.2.0. Its recorded configuration uses 20 training epochs, a training batch size of eight, SGD with a learning rate of 0.01, cosine learning-rate scheduling and a seed-controlled data split. The exported runtime artifact is versioned independently of local training checkpoints.

The metadata defines class index zero as No Fall and index one as Fall. A temporal prediction opens an incident when the Fall probability reaches at least 0.50. After an incident, three consecutive predictions below 0.35 are required to re-arm the detector. This clear rule suppresses repeat alerts from overlapping windows; it does not specify when a physical fall ends or prove that the person has recovered.

| Component | Implemented responsibility |
| --- | --- |
| Model process | Spawned CPU inference process with bounded cancellation and restart |
| API and storage | FastAPI jobs, SQLite metadata and owned media/results |
| Browser | React video and pose overlay, timeline and report downloads |
| Resource control | Visitor/network admission, queue cap and reserved job-file budget |

### 3 4 Preprocessing Compatibility

A numerical Gaussian-kernel comparison against the pinned MMAction2 v1.2.0 source found a maximum absolute difference of 0.003454 across four diagnostic coordinate/score cases. This comparison isolates the heatmap stencil and does not establish full preprocessing parity. The deployed bridge uses a rolling four-second window, whereas the original validation configuration samples the clip. Crop rounding, coordinate validity and temporal coverage require paired validation-data comparison before a model-level equivalence claim or preprocessing change.


<!-- page break -->

## 4 Dataset

### 4 1 Source and Composition

The project owner identifies the training data as the Fall Video Dataset published by payutch on Kaggle. Public metadata checked on 10 October 2026 identifies version one, approximately 16.1 GB and a CC0 label. The description names three upstream collections: Fall Vision on Harvard Dataverse, a Figshare activity dataset involving 29 subjects, and the Montreal multiple-camera fall dataset. The aggregator label does not independently verify each source recording or its redistribution rights.

| Historical cleaning stage | Samples |
| --- | --- |
| Original Fall video and pose pairs | 3,140 |
| Original No Fall video and pose pairs | 3,848 |
| Original total | 6,988 |
| Empty pose CSVs removed | 29 |
| Final after exact-pose deduplication | 6,766 |
| Final Fall / No Fall | 3,059 / 3,707 |

### 4 2 Preprocessing and Partitioning

The recorded dataset pairs videos with frame-aligned COCO-17 keypoint CSV files in Fall and No_Fall folders. Cleaning checks usable poses and removes exact-pose duplicates. Derived groups are kept within the same partition. The reported split contains 4,742 training, 1,013 validation and 1,011 test samples. Reliable participant identifiers were not supplied with the retained split evidence, so the evaluation is group-aware rather than confirmed subject-independent.

The two local six-second demonstration clips are separate diagnostic inputs. Their previous source/license and onset claims were unsupported and have been removed. Public API exposure is gated until the actual source, rights and independent labels are verified. Original split metadata and held-out prediction files are still needed to reproduce historical metrics; the Kaggle URL alone does not reconstruct those artifacts or the exact training run.


<!-- page break -->

## 5 Results and Analysis

### 5 1 Historical Classification Results

The historical held-out evaluation comprises 1,011 samples at a threshold of 0.50. These values are project-recorded classifier results, not measurements newly reproduced by the two diagnostic executions or by a deployed monitoring service.

| Metric | Reported value |
| --- | --- |
| Fall precision | 97.09% |
| Fall recall | 94.75% |
| Fall F1 | 95.90% |
| Balanced accuracy | 96.20% |
| Overall accuracy | 96.34% |
| Average precision | 99.61% |

Figure 2  Historical confusion counts for the group aware held out split

The confusion counts are 541 true negatives, 13 false positives, 24 false negatives and 433 true positives. Fall precision is 433 divided by 446; recall is 433 divided by 457. The 24 missed fall labels demonstrate why accuracy alone does not describe the cost of failures. Activity-specific causes require inspection of the original misclassified clips. A separately analysed test-set threshold of 0.4039 is not used for deployment, because selecting a threshold on held-out test labels would bias its evaluation.


<!-- page break -->

## 5 Results and Analysis

### 5 2 Model Behaviour Across Executions

Both diagnostic clips were processed through the actual isolated CPU model and API on 10 October 2026. Each lasts six seconds. The fall clip produced 36 poses, six temporal predictions and one incident. The normal clip produced 26 poses, four predictions and no incident. The inputs retain descriptive diagnostic labels; independent ground truth and source permission are not inferred from model output.

Figure 3  Actual ONNX confidence records on the source video timeline

| Fall clip source time | Fall probability | Observed decision |
| --- | --- | --- |
| 2.00 s | 0.0101 | Below threshold |
| 4.50 s | 0.0061 | Below threshold |
| 5.33 s | 0.9349 | Incident opened |
| 5.83 s | 0.9710 | Same incident retained |

The increase near 5.33 seconds occurs after four low-confidence windows and remains high in the final window. The final record is important because completion must not discard late evidence. The incident count remains one because the detector has not re-armed. The normal execution remains below the threshold. The recordings are too small to calculate population accuracy, and the removed onset annotation means 5.33 seconds is a detection timestamp rather than a measured physical-event delay.


<!-- page break -->

## 5 Results and Analysis

### 5 3 Extracted Features and Signal Interpretation

The runtime extracts joint coordinates and raw scores, then derives motion urgency and pose reliability as instrumented signals. Urgency combines normalized hip descent, torso rotation, joint displacement and bounding-box aspect change. Reliability combines confidence, visible-joint coverage, torso visibility, temporal stability and frame containment. The temporal classifier consumes heatmaps; neither signal currently controls model scheduling.

Figure 4  Actual urgency and reliability records during both diagnostic executions

In the fall execution, urgency rises to approximately 0.622 at the first detected incident, while reliability is approximately 0.777. The previous recorded window at 4.50 seconds has urgency approximately 0.208 and fall probability approximately 0.006. These observations show that geometric motion indicators and temporal classification provide different information. They do not prove that urgency predicts a fall independently or that a particular signal threshold is calibrated.

The normal execution includes ten sampled frames without a detected person. Its 26 valid poses support four temporal predictions rather than one prediction for every frame. This illustrates the separation between configured sampling, pose availability and classifier cadence. Browser overlays clear when a matching pose is unavailable, and confidence uses the latest valid record at or before playback time. Missing confidence is not replaced with zero, and future predictions are not displayed prematurely.

Feature values can help select recordings for error inspection, but attribution must remain conditional. A reliability reduction may reflect visibility, framing or unstable joints; identifying its cause requires reviewing the corresponding video and pose sequence. Matched ablations of urgency/reliability-guided scheduling remain unperformed, so no computational saving or sensitivity improvement is reported.


<!-- page break -->

## 5 Results and Analysis

### 5 4 Processing Performance and Resource Use

The execution environment was Windows with Python 3.11.16, ONNX Runtime 1.29.0, RTMLib 0.0.16 and twelve logical CPU processors. The CPU identification reported Intel64 Family 6 Model 186 Stepping 3. Both clips ran sequentially in the same service after model initialization. Resource values refer to the model process and were sampled during execution; they are not whole-machine or GPU measurements.

| Measured quantity | Fall clip | Normal clip |
| --- | --- | --- |
| Video duration | 6.00 s | 6.00 s |
| API processing time | 22.515 s | 16.922 s |
| Sampled-frame throughput | 1.604 FPS | 2.141 FPS |
| Mean PoseC3D call time | 1172.4 ms | 1227.4 ms |
| Mean pose inference time | 367.0 ms | 356.7 ms |
| Mean process CPU | 759.6% | 742.0% |
| Peak sampled resident memory | 460.3 MB | 433.5 MB |
| Temporal model calls | 6 | 4 |

Process CPU uses one logical processor as 100%, so values above 100% represent execution across several processors. The observed means correspond to approximately 7.6 and 7.4 processor-equivalents; they must not be described as 760% of the entire machine. Resident-memory peaks are sampled and may miss shorter unsampled peaks. GPU utilization is not applicable to this CPU execution.

The configured six samples per source second differs from measured throughput of approximately 1.60 and 2.14 sampled frames per wall-clock second. Processing therefore exceeds the six-second video duration. These single executions do not establish a latency distribution or hosting capacity. Event-delay percentiles remain unavailable without independently annotated onset, and false alarms per hour remain unavailable without sufficient verified normal-camera exposure. Classifier call time must not substitute for either measure.


<!-- page break -->

## 5 Results and Analysis

### 5 5 Issues Verification and Validity

| Observed issue or evidence gap | Correction or remaining limitation |
| --- | --- |
| Proxy origin mismatch | Browser Host is preserved in development and nginx routing |
| Playback used future or stale records | Source-time selection, seek updates and pose-gap clearing |
| Polling/result failures | Bounded retries and explicit retry of the same job |
| Concurrent queue/storage requests | Atomic admission and result-size reservation enforcement |
| Native model hang or crash | Isolated process termination and model restart |
| Invalid numeric or pose output | Reject before completed results are published |
| Evaluation counted failures as normal | Failures and unverified labels excluded from classification |
| Unsupported clip metadata | Source/onset claims removed; public examples gated |

Automated verification ran 108 Python tests, with 104 passing and four optional ONNX-environment checks skipped. Separate actual-model API executions supplied the measured traces. Twelve frontend tests passed, including eight DOM journey tests covering completion, downloads, seeking, retry, cancellation, oversized uploads and unmounting. The production frontend build and lint checks also passed. Process tests exercise deliberately hung and crashed adapters; those adapter outputs are not classifier evidence.

The strongest supported conclusion is that the measured prototype completes a traceable local video-analysis workflow and exposes explicit failure states. A newly reproduced held-out evaluation, independent subject coverage, broader hard-negative recordings and matched ablations remain absent. The numerical kernel discrepancy prevents a full-preprocessing parity claim. Docker configuration validates, but container execution and public HTTPS release remain pending. These limitations constrain the report without being replaced by invented measurements.


<!-- page break -->

## 6 Innovation and Novelty

### 6 1 Implemented Engineering Contribution

The contribution is the integration of temporal pose inference with a private, inspectable and recoverable browser workflow. Source-coordinate poses, temporal probabilities and incident records remain aligned with the original video. A result carries the model hash, processing measurements and downloadable records. Each clip receives independent engine state, and anonymous browser ownership separates private uploads and reports.

The service uses a spawned model process so an unresponsive native call can be terminated without executing heavy inference in an HTTP request handler. Atomic admission reserves queue and storage capacity before multipart parsing, with visitor and network windows that survive deletion of a result. This addresses specific operational failures in the local implementation and provides a reproducible basis for further evaluation.

### 6 2 Proposed Advantages and Evidence Required

| Proposed advantage | Evidence status |
| --- | --- |
| Temporal pose decisions capture movement | Implemented; matched comparison with image-only baseline pending |
| Inspectable traces make errors reviewable | Actual confidence and signal records available |
| Incident de-duplication limits repeated events | Implemented semantics and regression coverage; larger event study pending |
| Urgency/reliability may guide efficient scheduling | Signals implemented; adaptive policy and ablation not evaluated |
| Reliable public research demonstration | Local workflow verified; deployed HTTPS verification pending |

YOLOX, RTMPose and PoseC3D are established model families. Their reuse and fine-tuning do not constitute a new backbone architecture. The project may improve practical inspection and execution control relative to its earlier prototype, but no statistically supported accuracy or latency superiority over an external system has been demonstrated. A future comparison should fix recordings, partitions, thresholds, hardware and concurrency, then measure missed events, false alarms and resource cost together.


<!-- page break -->

## 7 Conclusion

ICare implements a temporal pose-based fall-analysis pipeline and a browser experience for short recorded videos. The retained historical group-aware evaluation reports 95.90% fall F1 and 96.34% overall accuracy. Those results support the recorded classifier experiment but do not establish subject-independent generalization or deployed reliability. The current verification adds direct evidence that actual model outputs complete through the isolated API and remain inspectable as source-time confidence, extracted motion signals and incident records.

In the two local diagnostic executions, the fall-labelled clip generated one incident and the normal-labelled clip generated none. Processing took 22.52 and 16.92 seconds, with sampled resident-memory peaks of 460.3 and 433.5 MB. These are limited single-run observations. They support integration and resource analysis without providing a new accuracy estimate, event-delay distribution or monitoring false-alarm rate.

The main completed engineering outcome is a reproducible workflow with independent clip state, private results, bounded admission, truthful playback and recoverable model execution. Remaining scientific inputs include original split/prediction artifacts, paired preprocessing validation, verified example provenance and independently annotated broader recordings. The deployment owner must build and exercise the supplied container configuration, establish HTTPS and operational limits, and verify the public service before adding a live-release result.

ICare remains a research prototype. Its outputs support analysis and demonstrations; they do not provide medical diagnosis or an emergency response service. The report concludes with evidence-backed local behavior and explicit limits rather than unsupported novelty or operational guarantees.

### Sources and Evidence

1  Fall Video Dataset by payutch on Kaggle, version 1. https://www.kaggle.com/datasets/payutch/fall-video-dataset

2  MMAction2 v1.2.0 PoseC3D configuration and pose transforms. https://github.com/open-mmlab/mmaction2/tree/v1.2.0

3  ICare project records and local execution evidence, 10 October 2026. ONNX SHA256 begins 2b2c0e8b7245; historical split 4742 training, 1013 validation and 1011 test.
