# ICare

[![CI](https://github.com/vihaanbishnoi/ICare/actions/workflows/ci.yml/badge.svg)](https://github.com/vihaanbishnoi/ICare/actions/workflows/ci.yml)

**Pose-based fall detection with local CPU inference and a React dashboard.**

ICare combines YOLO26n-pose and PoseC3D to estimate fall probability from body
movement over time.

[Interface preview](https://vihaanbishnoi.github.io/ICare/) · [Run locally](#run-locally) · [Architecture](#architecture)

The public website is a static preview. Run locally for camera and video inference.

## Features

- **Live detection:** camera frames, skeleton overlays, fall probabilities, and incident history.
- **Video analysis:** MP4 uploads, progress/cancellation, synchronized playback, and JSON/CSV reports.
- **Dashboard:** responsive layout, light/dark themes, and keyboard-accessible mode selection.
- **Multiple people:** every person tracked with their own ID, pose window and fall alerts.
- **Backend:** isolated model execution, bounded queues, session-scoped results, and duplicate-alert suppression.

## Stack

**Python 3.11 · FastAPI · SQLite · React 19 · TypeScript · Vite · ONNX Runtime · OpenCV**

## Architecture

```mermaid
flowchart LR
    UI[React dashboard] --> API[FastAPI]
    API --> Engine[Isolated model process]
    Engine --> Pose[YOLO26n-pose]
    Pose --> Heatmaps[Temporal joint heatmaps]
    Heatmaps --> Model[PoseC3D]
    Model --> Results[Predictions and incidents]
    Results --> API
    API --> UI
```

Camera and video share one temporal pipeline: 17 body joints are buffered over
up to four seconds and resampled to 48 positions for classification. Every person
in view is tracked and classified separately (see below). Inference runs outside
HTTP handlers; SQLite stores job and incident metadata.

Entry points: [`create_app()`](src/icare/api/main.py) and
[`load_engine()`](src/icare/inference/engine.py).

## Multiple people

One YOLO26n-pose pass finds every person in a frame. Each person gets a
persistent ID (`track_id`, shown as "Person 1", "Person 2", ...) matched from box
overlap and joint continuity with a short constant-velocity prediction, so people
who cross paths keep their IDs and an ID survives up to 2 s of occlusion
(`track_max_age_seconds`). Near-identical duplicate boxes for one person are merged.

Each person has their own four-second pose window, PoseC3D prediction every
0.75 s and incident rule (P(Fall) >= 0.50 opens an incident; three of that
person's predictions below 0.35 re-arm it). One person's movement never enters
another person's model input, and one person's open incident never suppresses,
clears or delays anyone else's, so simultaneous and consecutive falls by different
people are separate events. With one person in view, poses and predictions are
identical to the previous single-person pipeline (checked on the development clips). Poses, predictions, incidents and both report
formats include `track_id`; existing databases gain the column automatically.

PoseC3D costs about 0.2 s per person per prediction on a laptop CPU. Recorded
videos classify everyone; a live camera frame classifies at most two due people,
most overdue first, so a crowd slows each person's prediction rate instead of
stalling the stream. `ICARE_FALL_CONFIRMATIONS=2` requires two consecutive high
predictions per person before an incident (default 1, the baseline rule).

ICare does not label postures such as sitting, bending or lying: PoseC3D outputs
only P(Fall), and posture rules would need labelled data to validate. Per person,
the reported states are warming up (fewer than six poses spanning 2 s), monitoring,
and fall recorded (until re-armed).

## Run locally

Requires **Python 3.11** and **Node.js 24+**. Both ONNX models are included.
From the repository root in PowerShell:

```powershell
# Create once; skip this line if the environment already exists.
conda create -n icare python=3.11
conda activate icare
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
python -m uvicorn icare.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal, from the repository root:

```powershell
cd src/frontend
npm ci
npm run dev
```

Open the Vite URL and choose **Live detection** or **Analyze video**. Keep both
terminals running; press **Ctrl+C** to stop. On later runs, skip installation.

Uploads default to **50 MB / 60 seconds**. One source uses inference at a time;
stop the camera before analyzing a video. Camera access requires localhost or HTTPS.

[Model readiness](http://127.0.0.1:8000/api/v1/ready) · [Configuration](.env.example)

## Evaluation

The current YOLO26n-pose + PoseC3D pipeline has **not been evaluated on labelled
videos**. Historical classifier results predate the pose-estimator change and
were group-aware, not verified subject-independent. Real-time performance and
preprocessing parity are unverified.

`python -m icare.evaluation.multi_person_eval --fall-clip F.mp4 --normal-clip N.mp4`
builds composite multi-person videos from real footage (a person falling, walking,
standing still or lying, tiled side by side or in a 3 × 2 grid, with time offsets
and an occluder), runs the real models and scores per-person events against the
tile labels. On the two development clips (one fall montage, one distant walker),
across 12 composite and 2 original videos:

| Pipeline | Falls detected | False or duplicate alerts | Median / max delay after onset |
| --- | ---: | ---: | --- |
| Per-person tracking (this version) | 23 / 24 | 0 | 0.97 s / 1.8 s |
| Largest person only (previous) | 3 / 24 | 0 | 0.63 s / 0.63 s |
| Per-person tracking, `ICARE_FALL_CONFIRMATIONS=2` | 23 / 24 | 0 | 1.63 s / 2.63 s |

Every tracked person was detected in at least 97.9 % of sampled frames, except
while deliberately hidden; IDs switched only inside the montage's cross-dissolve,
where two different people are briefly visible. The miss is a person who appears 1.8 s before the video ends,
too short for a 2 s window; it is detected when they stay in view. These are
composites of two clips with one actor per tile, so they test tracking, isolation
and event logic with real model outputs, not accuracy on real crowded scenes,
sitting, bending, kneeling, furniture occlusion or people of different builds.
Those need labelled multi-person recordings.

Training records reference the [Fall Video Dataset](https://www.kaggle.com/datasets/payutch/fall-video-dataset).
Classifier export provenance remains unresolved due to conflicting checkpoint
records. See [model metadata](models/posec3d_runtime.json) and
[pose export metadata](models/yolo26n-pose.json).

Research prototype; not a medical device or emergency service.
The upstream pose-model [license](models/YOLO26_LICENSE) is included.

<details>
<summary>Development and static preview</summary>

From the root: `python -m icare.tools.check_repository` and
`python -m unittest discover -s tests -t .` (tracking, per-person events, API,
storage migration and the real ONNX models; synthetic scenes test plumbing, not
fall accuracy).
From `src/frontend/`:

```sh
npm run lint
npm run build
npm run build:static
npm run preview:static
```

The static preview opens under `/ICare/`. Its homepage plays a recorded
demonstration of the local app from `src/frontend/public/demo.mp4`; until that
file exists it shows "Demo recording coming soon." It is the only video the
static build accepts, and must be a real screen recording of ICare (keep it small;
GitHub rejects files over 100 MB). With Pages enabled and
`ICARE_PAGES_ENABLED=true`, passing changes merged into `main` deploy automatically.
CI runs repository checks, the Python tests, lint, both builds, and credential
scanning. Verify local inference on real footage before demonstrating it.

Source: [`inference/`](src/icare/inference/), [`api/`](src/icare/api/),
[`frontend/`](src/frontend/). Optional experiments live in
[`evaluation/`](src/icare/evaluation/); model-export dependencies are separate in
`requirements-export.txt`.

</details>
