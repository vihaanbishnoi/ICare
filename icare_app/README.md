# Retained model baseline

The abandoned UI/launcher were removed; this package is not a web application.
Use [component decisions](../docs/project/component_decisions.md) and the
[v1 engine contract](../docs/interfaces/inference.md).

| Module | Use | Part |
| --- | --- | --- |
| pose.py | Reusable detection/pose operations; optional live worker reference | Person 1 |
| onnx_backend.py | Existing ONNX execution coupled to state that needs separation | Person 1 |
| posec3d_bridge.py | Temporal resampling and heatmaps | Person 1 |
| pose_signals.py | Urgency/reliability instrumentation | Person 1 with Person 4 validation |
| inference.py | Probability/event data and rules; not ready API orchestration | Person 2 |
| reports.py | Field meanings/export reference; not private job storage | Person 2 |
| subject_audit.py | Subject-overlap evidence | Person 4 |

The simulated-event helper and frame-overlay/session methods in the retained
reference must not be used as public model results. Person 2 starts orchestration
fresh. Person 1 starts deterministic offline processing from useful operations
rather than the old live queue.

No ui.py or app.py exists. Do not restore them to make a shortcut demo.
New API/frontend stay in their own boundaries, and actual startup is documented
when implemented. Model/class/preprocessing meaning stays stable unless Person 4
validates a change.
