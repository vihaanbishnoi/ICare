# ICare fall-detection portfolio project

This repository contains:

- `up_fall_kaggle_baseline.ipynb`: staged UP-Fall preparation and RTMPose extraction notebook.
- `app.py`: local Gradio application with FastRTC webcam streaming, video upload, incident display, and JSON/CSV reporting.
- `icare_app/inference.py`: model boundary and temporal incident state machine.

## Run the local interface

Use Python 3.10 or 3.11 in a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:7860` and grant camera permission when prompted.

## Validate RTMPose locally

The first run downloads the lightweight YOLOX-tiny person detector and RTMPose-s
COCO-17 ONNX models. In PowerShell:

```powershell
$env:ICARE_ENABLE_RTMPOSE = "1"
$env:ICARE_POSE_DEVICE = "cpu"
python app.py
```

The live and uploaded-video views will show the selected person's bounding box
and skeleton. This stage intentionally makes no fall prediction until the trained
PoseC3D checkpoint is connected. `YOLOX` is used only for person detection; pose
keypoints come from RTMPose.

Pose inference runs on a background latest-frame worker. FastRTC also skips stale
frames before invoking the callback. Waiting frames are overwritten rather than
queued, inference uses a maximum width of 416 pixels, and
the person detector runs every five pose samples while the last box is reused in
between. The displayed camera therefore stays current even when CPU inference is
slower than the camera frame rate.

`icare_app/posec3d_bridge.py` contains the timestamp-aware 48-frame rolling
buffer and converts COCO-17 poses into the `1 x 17 x 48 x 64 x 64` joint-heatmap
tensor expected by the fine-tuned PoseC3D model. Runtime settings are recorded in
`models/posec3d_runtime.json`. The final ONNX model will consume this tensor.

After Kaggle training, run the notebook's ONNX export cells and download
`/kaggle/working/posec3d_fall/posec3d_fall.onnx`. Place it at
`models/posec3d_fall.onnx` and restart `python app.py`. The app detects the file
automatically and enables real binary fall probabilities; no environment flag is
required. Keep the exported checkpoint/config and evaluation metrics alongside
the ONNX file for reproducibility.

## Current model status

The interface intentionally uses `UnconfiguredBackend`. It does not generate fake fall predictions. The **Inject demo fall event** control tests the incident timeline and report downloads without pretending that a model produced the event.

After RTMPose and PoseC3D training is complete, implement the `InferenceBackend` contract in `icare_app/inference.py` and replace `UnconfiguredBackend` in `app.py`. The backend owns pose extraction, rolling-window sampling, PoseC3D inference, and the 11-class probability vector. The existing session layer handles fall-probability aggregation, confirmation, cooldown, and reporting.

Generated JSON and CSV reports are written under `artifacts/reports/`.
