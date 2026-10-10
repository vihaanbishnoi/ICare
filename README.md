# ICare — Pose-Based Fall Detection

ICare is a pose-based fall-detection model baseline being developed into a public
video-analysis demo. It uses person detection, pose estimation, and a temporal
action-recognition model instead of classifying isolated RGB frames.

> **Safety:** This is not a medical device, emergency service, or production monitoring system. Do not perform real falls on a hard surface when testing.

## Start here

The engine, FastAPI API and React example/upload flows work locally. Read
[implementation status](docs/project/implementation_status.md) for verified
checks and remaining inputs, then [local startup](#run-locally).

Development is handled by the project owner and coding assistant. Person 5 owns
hosting, HTTPS, operational configuration and the live release. The former
five-person collaboration process is retired; see [development](docs/development.md)
and [deployment](deployment/README.md).

Target: a public no-login research demo with permitted examples, short uploads,
real pose/confidence/incident results and truthful performance evidence. Public
hosting and example provenance remain pending. The old Gradio UI stays removed.

The completed [academic report](docs/project/ICare_Report.docx) follows the teacher
notes, with [editable text](docs/project/report.md) and actual model execution traces.
Unverified example clips are disabled by default; use permitted uploads, or
ICARE_ALLOW_UNVERIFIED_EXAMPLES=1 for local diagnostics only.

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

## Legacy live-worker reference

- This section describes the retained live-worker reference. The active
  example/upload engine instead samples source video at 6 FPS, detects every
  sampled frame and processes the final window; see [engine guide](icare_app/ENGINE.md).
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
api/                         FastAPI jobs, ownership, media and reports
frontend/                    React/TypeScript/Vite browser demo
evaluation/                  benchmark and robustness tooling
configs/                     Deployment owner (Person 5) future product configuration, README only
icare_app/                   existing reusable runtime and prototype references
  inference.py               probability, session, and incident logic
  engine.py, engine_model.py v1 offline engine for the API (see icare_app/ENGINE.md)
  pose.py                    YOLOX + RTMPose operations and legacy live worker
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
docs/development.md          development scope and verification
docs/project/                reuse/replace decisions, architecture, evidence, report
docs/security/               credential review and security findings
deployment/                  Deployment owner (Person 5) hosting/integration/security and runbook
research/                    future approved notebooks and experiment configs
examples/                    catalog and two clips; verify provenance before release
.github/                     CI, credential scan and issue/PR templates
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

Start the real API from the repository root. Initial model loading may download
pose weights and take time; `/api/v1/ready` returns 503 until the model is ready.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r api/requirements.txt
.\.venv\Scripts\python.exe -m tools.check_repository
.\.venv\Scripts\python.exe -m uvicorn api.main:create_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal, use Node 24 or newer and start the frontend:

```powershell
cd frontend
npm ci
npm run dev
```

Open the URL printed by Vite. Its same-origin proxy preserves Host and forwards
`/api/v1` to port 8000. Set `ICARE_API_TARGET` in the frontend terminal if using
a different API port. `.env.example` lists supported environment variables;
export them in your shell or host configuration (the API does not auto-load .env).
The engine entry point remains `icare_app.engine.load_engine` ([guide](icare_app/ENGINE.md)).

With Docker running, `docker compose up --build -d --wait` serves the whole
site at `http://127.0.0.1:7860` (add `ICARE_ALLOW_UNVERIFIED_EXAMPLES=1` locally
to enable the two example clips, then `deployment/smoke_test.sh`). The container
build, run and smoke test are verified locally and in CI; public HTTPS is pending.
See [deployment](deployment/README.md) and [runbook](deployment/runbook.md).

## Check before opening a PR

```powershell
.\.venv\Scripts\python.exe -m tools.check_repository
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

GitHub workflows run repository checks, unit tests on Windows and Linux, and
credential scanning, plus frontend tests/build. These files take effect after
they are pushed to GitHub. From frontend/, run `npm test` and `npm run build`.
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
