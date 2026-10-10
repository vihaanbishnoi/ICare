# Components kept removed or rebuilt

Preparation now removes the abandoned web layer rather than making five AI
sessions repair it. Model computations, trained weights, incident-rule references,
and baseline tests remain. The subsequent CPU engine, FastAPI API and React
frontend are implemented; see [current status](implementation_status.md).

| Component | Current decision | Responsible part |
| --- | --- | --- |
| ONNX weights and runtime metadata | Keep and verify | Development; claims checked by Development |
| YOLOX/RTMPose and heatmap operations | Keep useful computation | Development |
| Pose worker/ONNX state coupling | Selectively refactor for deterministic offline processing | Development |
| Incident thresholds/deduplication | Reuse semantics, build isolated orchestration | Development |
| Gradio UI and root app.py | Removed from active source | New API Development, new frontend Development |
| Shared UI globals/reset wiring | Removed with UI | Do not recreate them |
| Frame-dropping upload callback loop | Removed with UI | Development supplies deterministic engine; Development completes jobs correctly |
| Timer-generated report writes | Removed with UI | Development materializes owned results |
| reports.py predictable filename helper | Retained field reference, not product storage design | Development rewrites per-job ownership/paths |
| Simulated preview UI | Removed; reference helper must never become a public API | Development |
| Urgency/reliability signals | Retained instrumentation | Development; evaluated by 4 |
| Adaptive scheduler | Deferred | One later matched experiment, not essential release |
| Subject audit and unit tests | Kept | Development and relevant component owners |
| Historical metrics | Kept with group-aware limits | Development |
| Removed notebooks/demo media | Stay deleted | Development obtains needed approved assets |
| Extra behaviours/paper/patent | Deferred | Core example/upload release first |

Gradio and FastRTC were removed from root requirements. A local ignored backup of
the removed launcher/UI exists in artifacts/legacy_gradio_snapshot/; it is not
part of the shared project or a template for the replacement.

The loose best_acc_top1_epoch_12.pth checkpoint was moved from the repository root
into ignored artifacts/checkpoints/ on the preparation machine. It is not the
deployable model and is not included in the handoff. Use the versioned ONNX and
runtime metadata under models/; do not let an AI choose a random local checkpoint.

## Avoid wasting AI coding time

Use the [default stack](stack.md), [v1 contracts](../interfaces/README.md), and
[one role prompt](../development.md). Do not generate a second architecture,
restore removed callbacks, rebuild pretrained model families, or retrain to
compensate for a folder change.

Development extends offline engine lifecycle, not GUI callbacks. Development extends
isolated jobs/API/storage; Development extends the working React/TypeScript/Vite app.
Retain mathematical operations/evidence and replace coupled orchestration.

Working local web startup is in the root README and API/frontend guides. Person
5 verifies container startup and public HTTPS hosting. Keep model
and preprocessing changes traceable to validation rather than claiming every
reference behavior must remain compatible.
