# ICare — Pose-Based Fall Detection

ICare is a pose-based fall-detection model baseline being developed into a public
video-analysis demo. It uses person detection, pose estimation, and a temporal
action-recognition model instead of classifying isolated RGB frames.

> **Safety:** This is not a medical device, emergency service, or production monitoring system. Do not perform real falls on a hard surface when testing.

## Team start here

**Read the [clean handoff](docs/team/handoff.md) first.** It gives each numbered
part its first task, inputs, outputs, and completion proof. The
[proposal checklist](docs/product/proposal_coverage.md) maps the supplied plan
to the five parts. Use deeper documents only when your task needs them.

Target: a public, no-login recruiter demo with approved fall/normal examples,
short-video upload, real visual results/incidents, measured performance, and
reproducible deployment. Webcam and extra behaviours are later work.

Current status: retained inference/evaluation baseline; public URL and approved
example videos are pending. The old Gradio UI and launcher have been removed;
no new API/frontend is implemented by this preparation work.
Read the [product brief](docs/product/brief.md), [component decisions](docs/project/component_decisions.md),
and [release criteria](docs/product/release_criteria.md).

| Part to choose | Complete responsibility |
|---|---|
| [Person 1](docs/team/person_1.md) | Inference engine and model runtime |
| [Person 2](docs/team/person_2.md) | API jobs, incidents, and private results |
| [Person 3](docs/team/person_3.md) | Public frontend and demo experience |
| [Person 4](docs/team/person_4.md) | Dataset, evaluation, benchmarks, examples, and evidence |
| [Person 5](docs/team/person_5.md) | Deployment, security, integration, release, and final documentation |

All five usernames are in an [unassigned roster](docs/team/roster.md). Teammates
choose their parts; no username is mapped to a role. Person 5 coordinates the
board, integration, README, and combined report, so there is no sixth workstream
assigned to the project owner.

For ChatGPT/Codex or Claude, start with the [AI workflow](docs/team/ai_workflow.md)
and [copyable role prompts](docs/team/prompts/README.md). Shared instructions are
in [AGENTS.md](AGENTS.md), imported by [CLAUDE.md](CLAUDE.md).
Use the [default stack](docs/project/stack.md) and [v1 contracts](docs/interfaces/README.md)
so independent AI sessions do not create incompatible components.

The [handoff](docs/team/handoff.md), [ownership](docs/team/ownership.md),
[backlog](docs/team/backlog.md), and [contribution guide](CONTRIBUTING.md)
cover collaboration. CODEOWNERS has no active assignments until
the team chooses; use manual reviews meanwhile. The [documentation index](docs/README.md)
links the full plan.

The former demo media and training notebooks were intentionally removed from the
working tree. Future approved demo assets belong in `examples/`, and research
notebooks belong in `research/`. Neither folder is a training dataset.

## Pipeline

```text
Camera/video frame
  -> YOLOX-tiny person bounding box
  -> RTMPose-s COCO-17 keypoints
  -> timestamped rolling pose buffer
  -> resample to 48 temporal positions
  -> 17 x 48 x 64 x 64 joint heatmaps
  -> fine-tuned PoseC3D ONNX model
  -> P(No Fall), P(Fall)
  -> threshold and incident de-duplication
  -> on-screen result plus JSON/CSV report
```

YOLOX is used only to locate the person. RTMPose estimates the 17 COCO body joints. PoseC3D analyzes their movement over time.

## Model and dataset

The binary PoseC3D model was fine-tuned from an NTU60-pretrained SlowOnly-R50 PoseC3D checkpoint using MMAction2. The source dataset contained paired videos and pose CSVs under `Fall` and `No_Fall`:

| Audit stage | Samples |
|---|---:|
| Original fall pairs | 3,140 |
| Original no-fall pairs | 3,848 |
| Original total | 6,988 |
| Empty CSVs removed | 29 |
| Final samples after exact-pose deduplication | 6,766 |
| Final fall samples | 3,059 |
| Final no-fall samples | 3,707 |
| Unique derived groups | 4,786 |

The source dataset is not stored in this GitHub repository because it contains thousands of videos and must be obtained under its original distribution terms. The training data use the following structure:

```text
Fall/
  Raw_Video/
  Keypoints_CSV/
No_Fall/
  Raw_Video/
  Keypoints_CSV/
```

Each training video must have a matching, frame-aligned COCO-17 keypoint CSV. Supported dataset video extensions are `.mp4`, `.avi`, `.mov`, `.mkv`, `.mpeg`, `.mpg`, and `.m4v`. Adding a video to `examples/` or analyzing it in the app does not retrain the model; new training samples must be validated, included in regenerated metadata, and used in a new training run.

The group-aware split contained 4,742 training, 1,013 validation, and 1,011 test samples. It prevents derived duplicates/groups from crossing splits. Reliable subject IDs were not available, so this result must not be described as a true subject-independent evaluation.

The repository now includes a strict subject-overlap audit. It accepts a split
manifest only when at least 95% of rows have a verified subject identifier:

```powershell
python -m tools.audit_subject_split fall_pose_split_metadata.csv `
  --subject-column subject_id `
  --output artifacts/evaluation/subject_split_audit.json
```

See [evaluation status](docs/project/evaluation_status.md) for the current
finding and the evidence boundary.

### Held-out test results

The reported evaluation used a classification threshold of `P(Fall) >= 0.50`:

| Metric | Result |
|---|---:|
| Fall precision | 97.09% |
| Fall recall | 94.75% |
| Fall F1 | 95.90% |
| Balanced accuracy | 96.20% |
| PR-AUC / average precision | 99.61% |
| Overall accuracy | 96.34% |

Confusion counts were TN=541, FP=13, FN=24, and TP=433. A threshold of `0.4039` produced the highest observed F1 during a separate test-set analysis, but it is **analysis only** and is not used for deployment because selecting a threshold on test labels would bias the result. Final calibration should use validation data.

The exported ONNX model accepts `batch x 17 x 48 x 64 x 64` float heatmaps and returns `batch x 2` class probabilities. PyTorch/ONNX verification produced a maximum difference of approximately `2.8e-22`.

## Retained inference worker behavior

- This section describes retained library behavior, not a running browser app.
- A background worker retains only the newest pending frame; it never builds a latency-producing frame queue.
- Inference frames are resized to a maximum width of 416 pixels.
- YOLOX-tiny runs every third processed pose frame, with bounding-box reuse on the two frames between detections. It also runs immediately when no box exists.
- RTMPose-s runs for every frame accepted by the pose worker.
- The buffer retains up to four seconds of timestamped poses.
- Startup requires six successful poses spanning at least two seconds.
- Available poses are interpolated to the model's fixed 48-position input.
- PoseC3D runs at most once every 0.75 seconds (about 1.33 predictions/second).
- Motion urgency V1 combines normalized hip descent, torso rotation, joint displacement, and bounding-box aspect-ratio change.
- Pose reliability V1 combines keypoint confidence, visible-joint coverage, torso visibility, temporal stability, and frame containment.
- The live overlay displays urgency and reliability alongside pose-buffer status.

The central real-time design rule is to **drop stale frames instead of allowing latency to accumulate**. On a CPU, the camera can capture at 12 FPS while pose inference runs at a lower rate and still remain close to the current moment.

### Incident rule

A new incident is recorded immediately when one temporal PoseC3D prediction reaches:

```text
P(Fall) >= 0.50
```

For an evaluation recording, supply its independent expected outcome and
annotated fall-onset timestamp through the future job/evaluation interface.
An event can then record alert latency as
`alert timestamp - fall onset`. Without an annotation, alert latency remains
unknown rather than being estimated.

The JSON report contains every temporal-classifier record, including timestamp,
fall confidence, inference time, source pose count, urgency, reliability,
process CPU percentage, and resident memory. A separate
`*_inference.csv` file is written beside the incident CSV. The CPU percentage is
a process-level sample; the current ONNX configuration uses the CPU provider and
does not report GPU utilization.

After an incident, the detector is re-armed only after three predictions below `0.35`. This prevents overlapping four-second windows from recording the same physical fall repeatedly; the clear threshold is an internal de-duplication rule, not a reported fall-ending time.

## Repository structure

```text
api/                         Person 2 fresh API/job/incident boundary, README only
frontend/                    Person 3 fresh public UI boundary, README only
evaluation/                  Person 4 evaluation/benchmark boundary, README only
configs/                     Person 5 future product configuration, README only
icare_app/                   existing reusable runtime and prototype references
  inference.py               probability, session, and incident logic
  pose.py                    YOLOX + RTMPose latest-frame worker
  posec3d_bridge.py           temporal resampling and heatmaps
  onnx_backend.py            PoseC3D ONNX Runtime backend
  pose_signals.py             motion urgency and pose reliability
  reports.py                 JSON/CSV report generation
  subject_audit.py           subject-disjoint split verification
models/                      deployable ONNX model and runtime metadata
tests/                       focused unit tests
tools/                       evaluation commands and repository checks
docs/product/                recruiter demo scope and release acceptance
docs/interfaces/             v1 engine/API/measurement defaults
docs/team/                   five numbered briefs, unassigned roster, backlog
docs/project/                reuse/replace decisions, architecture, evidence, report
docs/security/               credential review and security findings
deployment/                  Person 5 hosting/integration/security and runbook
research/                    future approved notebooks and experiment configs
examples/                    future approved demonstration assets
.github/                     existing CI/scan, unassigned review rules, issue/PR templates
CONTRIBUTING.md               setup and collaboration workflow
AGENTS.md                    shared coding-agent instructions
CLAUDE.md                    imports shared instructions for Claude
requirements.txt             retained engine/evaluation dependencies
requirements-test.txt        separate test-only dependencies
```

Generated reports are written to `artifacts/reports/` and excluded from Git. Training checkpoints (`.pth`, `.pt`, `.ckpt`), environments, caches, and local test media are also ignored. The deployable ONNX model remains versioned.

## Motion urgency experiment

After placing validation videos in separate fall and no-fall directories, run:

```powershell
python -m tools.plot_motion_urgency `
  --fall-dir D:\data\validation\Fall `
  --no-fall-dir D:\data\validation\No_Fall `
  --count-per-class 10
```

The command samples video at 6 FPS by default and writes
`urgency_traces.csv` plus a 20-video urgency/reliability plot under
`artifacts/evaluation/urgency/`. The dataset is not stored in this repository,
so the complete 10+10 experiment must run where those validation videos are
available. Do not tune urgency constants on the held-out test set.

## Run locally

Python 3.11 is the tested local version.

There is no web launcher yet. The old UI was intentionally removed so the API
and frontend owners can start fresh. These commands set up and verify the
retained model/evaluation baseline:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tools.check_repository
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Person 1 supplies an explicit engine entry point; Persons 2/3 implement API/UI
startup; Person 5 verifies and documents combined/container startup. Existing
audit/evaluation commands still work when their required data are available.
The non-secret `.env.example` lists planned engine settings; loading/wiring
them is implementation work, not behavior already supplied by this preparation.

## Check before opening a PR

```powershell
.\.venv\Scripts\python.exe -m tools.check_repository
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

GitHub workflows run repository checks, unit tests on Windows and Linux, and
credential scanning. These files take effect after they are pushed to GitHub.
Unit tests use synthetic inputs and do not establish real-model accuracy,
webcam connectivity, or deployment readiness.

## Safe testing

Use prerecorded fall videos first. For live tests, keep the full body and landing area visible, use good lighting, and prefer a side or 45-degree camera angle. Only perform a controlled descent onto a thick mattress with another person present—never stage an uncontrolled fall.

Test hard negatives as well as falls:

- fast sitting;
- normal lying down;
- crouching;
- picking up an object;
- tying a shoe;
- leaving the frame;
- camera movement or occlusion.

Record live probabilities and expected outcomes before changing thresholds. Production threshold calibration must use validation recordings from the complete runtime pipeline, not the held-out test set.

## Limitations and next steps

- The current pipeline follows only the largest detected person.
- CPU pose throughput can be much lower than camera FPS.
- Live RTMPose poses may differ from the pose generator used for the dataset, creating a train/deployment domain gap.
- The custom ONNX preprocessing bridge should be compared against MMAction2 on real validation samples for exact parity.
- The reported split is group-aware, not confirmed subject-independent.
- Motion urgency and reliability are instrumented, but they do not control model scheduling yet. Controller thresholds must wait for validation traces.
- A production system requires subject-independent and environment-diverse evaluation, validation-based threshold calibration, multi-person identity tracking, alert delivery, privacy/security controls, and substantially more failure-mode testing.
