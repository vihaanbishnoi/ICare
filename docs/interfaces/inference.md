# Inference contract version 1

Person 1 implements the engine; Person 2 supplies isolated jobs; Person 4 reviews
measurement meaning. Implemented in icare_app/engine.py (details, error codes and
decisions: [icare_app/ENGINE.md](../../icare_app/ENGINE.md)); real pose models on a
real clip are not yet verified.

## Engine operations

Define a side-effect-free import and explicit create/load operation. Readiness
verifies existing model input/output names, two-class order, metadata and CPU provider.
No model/network initialization should happen merely by importing an API schema.

The new import boundary will be icare_app.engine, created by Person 1. Provide
load_engine(config) returning an engine with ready, analyze_video, and close.
analyze_video takes a validated video path plus on_pose, on_prediction,
on_progress callbacks and a job-local cancellation signal named cancel_event.
Return the final summary only after all selected frames and pending temporal
predictions are handled. These names are the implemented contract. Person 2 injects this engine without HTTP or GUI imports.

First release uses source-frame dimensions and COCO-17 coordinates. Offline
sampling defaults to 6 poses per source second; select reproducibly using video
timestamps rather than wall-clock decoding speed. Preserve the four-second
temporal window and 48 heatmap positions unless validated change evidence exists.

## Output records

| Field | Meaning |
| --- | --- |
| timestamp_seconds | source-video time in seconds |
| fall_probability | ONNX Fall class probability, verified class index 1 |
| bbox_xyxy | four original-source pixel coordinates |
| keypoints | 17 [x,y,confidence] entries in COCO order |
| frame_width/frame_height | original source dimensions |
| window_start_seconds | temporal window start |
| source_pose_count | actual contributing pose count |
| inference_ms | measured temporal model time, not alert latency |
| urgency/reliability | optional signals; missing is null |
| CPU/RAM samples | scope/units/sampling documented |

Person 1 maps resized inference coordinates back to the original source.
Emit only genuine model probabilities; no person/no sufficient window is unavailable
prediction, not a fabricated zero. Person 2 owns final incident/job reporting.

## Lifecycle

Explicit load -> independent job state -> process selected samples -> drain final
work -> emit completed summary -> release job resources. Cancellation/errors
release resources and return a distinct outcome. Reset rejects stale generation output.

Do not route offline jobs through the live frame-dropping worker. Share immutable
execution only behind a design preserving buffers/timing/output ownership.
Initially one worker processes one job at a time; tests must still show that
state does not carry across jobs. Higher concurrency requires measured capacity
and independence evidence.

Incident semantics retained for Person 2: threshold 0.50; rearm after three
predictions below 0.35. Changing thresholds requires validation evidence, not
test-label tuning. Urgency/reliability do not control scheduling in this first slice.

## Acceptance

Actual clip completion includes its final prediction before the API completes.
Repeated and independent clips cannot reset/mix output. Missing weights, invalid
video, no person, insufficient temporal coverage, cancellation, and model errors
remain distinct. Person 4 can reconstruct source and processing timelines.
