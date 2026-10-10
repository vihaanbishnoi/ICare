# Retained model baseline

The abandoned UI/launcher were removed; this package is not a web application.
Use [component decisions](../docs/project/component_decisions.md) and the
[v1 engine contract](../docs/interfaces/inference.md).

| Module | Use | Part |
| --- | --- | --- |
| engine.py, engine_model.py | **v1 offline engine** (`load_engine`, `analyze_video`); see [ENGINE.md](ENGINE.md) | Development |
| pose.py | Reusable detection/pose operations; live worker is legacy reference | Development |
| onnx_backend.py | Existing ONNX execution coupled to state that needs separation | Development |
| posec3d_bridge.py | Temporal resampling and heatmaps | Development |
| pose_signals.py | Urgency/reliability instrumentation | Development with Development validation |
| inference.py | Probability/event data and rules; not ready API orchestration | Development |
| reports.py | Field meanings/export reference; not private job storage | Development |
| subject_audit.py | Subject-overlap evidence | Development |

Uploaded clips go through `engine.py`, never the live worker below.

The simulated-event helper and frame-overlay/session methods in the retained
reference must not be used as public model results. Development starts orchestration
fresh. Development starts deterministic offline processing from useful operations
rather than the old live queue.

No ui.py or app.py exists. Do not restore them to make a shortcut demo.
New API/frontend stay in their own boundaries, and actual startup is documented
when implemented. Model/class/preprocessing meaning stays stable unless Development
validates a change.
