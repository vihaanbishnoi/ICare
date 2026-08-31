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

## Current model status

The interface intentionally uses `UnconfiguredBackend`. It does not generate fake fall predictions. The **Inject demo fall event** control tests the incident timeline and report downloads without pretending that a model produced the event.

After RTMPose and PoseC3D training is complete, implement the `InferenceBackend` contract in `icare_app/inference.py` and replace `UnconfiguredBackend` in `app.py`. The backend owns pose extraction, rolling-window sampling, PoseC3D inference, and the 11-class probability vector. The existing session layer handles fall-probability aggregation, confirmation, cooldown, and reporting.

Generated JSON and CSV reports are written under `artifacts/reports/`.

