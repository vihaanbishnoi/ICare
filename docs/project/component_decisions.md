# Components kept removed or rebuilt

Preparation now removes the abandoned web layer rather than making five AI
sessions repair it. Model computations, trained weights, incident-rule references,
and baseline tests remain. No new product implementation was added.

| Component | Current decision | Responsible part |
| --- | --- | --- |
| ONNX weights and runtime metadata | Keep and verify | Person 1; claims checked by Person 4 |
| YOLOX/RTMPose and heatmap operations | Keep useful computation | Person 1 |
| Pose worker/ONNX state coupling | Selectively refactor for deterministic offline processing | Person 1 |
| Incident thresholds/deduplication | Reuse semantics, build isolated orchestration | Person 2 |
| Gradio UI and root app.py | Removed from active source | New API Person 2, new frontend Person 3 |
| Shared UI globals/reset wiring | Removed with UI | Do not recreate them |
| Frame-dropping upload callback loop | Removed with UI | Person 1 supplies deterministic engine; Person 2 completes jobs correctly |
| Timer-generated report writes | Removed with UI | Person 2 materializes owned results |
| reports.py predictable filename helper | Retained field reference, not product storage design | Person 2 rewrites per-job ownership/paths |
| Simulated preview UI | Removed; reference helper must never become a public API | Persons 2 and 4 |
| Urgency/reliability signals | Retained instrumentation | Person 1; evaluated by 4 |
| Adaptive scheduler | Deferred | One later matched experiment, not essential release |
| Subject audit and unit tests | Kept | Person 4 and relevant component owners |
| Historical metrics | Kept with group-aware limits | Person 4 |
| Removed notebooks/demo media | Stay deleted | Person 4 obtains needed approved assets |
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
[one role prompt](../team/prompts/README.md). Do not generate a second architecture,
restore removed callbacks, rebuild pretrained model families, or retrain to
compensate for a folder change.

Person 1 repairs offline engine lifecycle, not GUI callbacks. Person 2 creates
jobs/API/storage fresh, not a wrapper around FallDetectionSession.process().
Person 3 builds React/TypeScript/Vite fresh, not another Gradio page.
Retain mathematical operations/evidence and replace coupled orchestration.

There is intentionally no working web command today. New startup belongs to the
actual API/frontend implementation and Person 5's integration docs. Keep model
and preprocessing changes traceable to validation rather than claiming every
reference behavior must remain compatible.
