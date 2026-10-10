# Inference engine (Development)

`icare_app.engine` is the v1 engine behind [inference contract v1](../docs/interfaces/inference.md).
It turns one video file into timestamped poses and PoseC3D fall probabilities, with
no HTTP, browser or GUI code. Development's API loads it through `api/engine.py`.

Status: P1A/P1B/P1C implemented and unit-tested; P1D (independence, reset, no
person, completion) is covered by `tests/test_engine.py`, with Development's review
still to come. Real YOLOX/RTMPose/PoseC3D completed both six-second catalog clips
through the API on 10 October 2026. See [integration evidence](../docs/project/implementation_status.md).
Synthetic test numbers remain labelled and do not establish accuracy.

## Use it

```python
import threading
from icare_app.engine import load_engine, EngineError

engine = load_engine({"model_path": "models/posec3d_fall.onnx", "device": "cpu"})
poses, predictions = [], []
summary = engine.analyze_video(
    "clip.mp4",
    on_pose=poses.append,            # one record per sampled frame with a person
    on_prediction=predictions.append,  # one record per PoseC3D window
    on_progress=lambda value: None,  # float in [0, 0.99] or None; may raise to cancel
    cancel_event=threading.Event(),  # set it to stop between samples
)
engine.close()
```

Try a real clip from the command line (writes only under ignored `artifacts/`):

```powershell
.\.venv\Scripts\python.exe -m tools.run_engine_clip path\to\clip.mp4 --output artifacts\engine\clip.json
```

`load_engine` accepts the API's `{"model_path", "device"}` mapping plus optional
`metadata_path`, `sample_fps`, `inference_width`, `prediction_interval_seconds`,
`max_pose_gap_seconds`, `detection_frequency`. Unknown keys raise `ValueError`.
`ICARE_INFERENCE_WIDTH` is used when `inference_width` is not given.

## What happens to a clip

1. **Sampling.** Sample slot *k* is at `k / sample_fps` source seconds (default 6/s)
   and is served by decoded frame `round(k * fps / sample_fps)`. A frame's timestamp
   is `frame_index / fps`. Wall-clock decoding speed never matters, so the same clip
   always gives the same samples. If `sample_fps >= fps`, every frame is used.
2. **Pose.** The frame is shrunk to at most 416 px wide, YOLOX-tiny finds the
   largest person, RTMPose-s gives 17 COCO keypoints. Boxes and keypoints are then
   mapped back to **original source pixels** before anything is emitted or buffered.
3. **Window.** Poses go into a timestamped buffer (4 s window, resampled to 48
   positions, 17x48x64x64 heatmaps). A window needs at least 6 poses spanning 2 s.
4. **Prediction.** After each pose, if the window is ready and at least 0.75 s of
   video time passed since the last prediction, PoseC3D runs. Cadence is therefore
   about 0.83 s with 6 samples/s.
5. **Drain.** After the last sample, the window ending at the last pose is classified
   even if 0.75 s has not elapsed. `analyze_video` returns only after this, so the
   final prediction always arrives before the API marks the job complete.
6. **Gaps.** If the person is missing for more than 1.0 s the track ends: the buffer
   and signal estimator restart, so a window never interpolates across an absence.

## Records (field names are the contract)

`on_pose`: `timestamp_seconds`, `bbox_xyxy` (4 floats), `keypoints` (17 x
`[x, y, confidence]`, COCO order), all in original source pixels.

`on_prediction`: `timestamp_seconds` (end of the window, source time),
`fall_probability` (ONNX class index 1, always in [0, 1]), `window_start_seconds`,
`source_pose_count`, `inference_ms` (PoseC3D call only; **not** alert latency),
`urgency`, `reliability` (instrumentation only; they do not control scheduling).

Returned summary: `duration_seconds` (decoded frames / fps), `frame_width`,
`frame_height` (of the decoded frames) and `metrics`. Metrics are measured values or
`None`, never an invented zero:

| Metric | Meaning |
| --- | --- |
| `source_fps`, `frames_decoded`, `frames_reported_by_container` | Source facts; a mismatch between the last two means truncation |
| `sample_fps_requested`, `sampled_frames` | Sampling actually applied |
| `frames_with_person`, `frames_without_person`, `track_resets` | Pose coverage |
| `posec3d_calls`, `mean_pose_inference_ms` | Model usage; pose time per sampled frame with a person |
| `engine_wall_seconds`, `processed_frames_per_second` | Sampled frames per wall-clock second of the engine call (pose + classifier) |
| `process_cpu_percent_mean/max` | Whole-process CPU % (all threads, may exceed 100), sampled at each prediction via psutil; `None` without psutil |
| `process_rss_mb_peak` | Process resident memory in MB, same sampling |

GPU is not used; no GPU metric is emitted (not applicable). CPU/RAM are
process-scope, so under the API they include the API process.

## Failures raise `EngineError` subclasses with a distinct `code`

| `code` | Cause |
| --- | --- |
| `model_unavailable` | At load: weights/metadata missing or failing verification, pose models not loadable, non-CPU device |
| `invalid_video` | Missing, unreadable or corrupt file; no usable frame rate; no decodable frame; resolution change |
| `no_person` | No sampled frame contained a person |
| `insufficient_temporal_coverage` | Poses found but never 6 poses over 2 s in one continuous track |
| `model_error` | Pose or PoseC3D failed, or returned a malformed / non-finite / out-of-range result |
| `cancelled` | `cancel_event` was set |
| `engine_closed` | `close()` was called |

Nothing is clipped or defaulted to hide a failure: no prediction means no record.

## Lifecycle and isolation

`load_engine` verifies everything before `ready` is true: metadata (class order
`["No Fall", "Fall"]`, `fall_class_index` 1, 17 joints, 48 positions, 64 px, sigma
0.6), the ONNX interface (input `pose_heatmaps` [batch,17,48,64,64], output
`probabilities` [batch,2], CPU provider only), and a real forward pass on an empty
window that must return two probabilities summing to 1. `model_version` is
`posec3d_fall.onnx@<first 12 hex of the file's SHA-256>`, so a swapped artifact
changes it. `describe()` returns the verified settings for provenance.

Each `analyze_video` call creates its own pose session (`RTMPoseExtractor.fork()`
shares the loaded models, not tracking state), temporal buffer, signal estimator and
counters, and discards them on return, error or cancellation. There is no shared
mutable clip state and therefore nothing to reset or to go stale. A lock admits one
clip at a time; extra callers wait (and can still be cancelled while waiting).
Raising concurrency needs measured capacity first. Exceptions from your callbacks
propagate after cleanup, which is how the API's `on_progress` cancels.

The old live `PosePreviewBackend`/`PoseC3DONNXBackend` frame-dropping worker is not
used and must not serve uploaded clips.

## Decisions for review

- **Detector runs on every sampled frame** (`detection_frequency=1`), unlike the
  live worker's every-third. At 6 samples/s a reused box would be at least 0.33 s
  stale during fast motion. Development: measure the speed/accuracy trade-off.
- **1.0 s gap resets the track.** The live code interpolated across any gap inside
  four seconds. `max_pose_gap_seconds=None` restores that.
- **`no_person` and `insufficient_temporal_coverage` fail the job** instead of
  completing with an empty prediction list, as the API README asks for distinct codes.
- **Timestamps are `frame_index / fps`** (constant frame rate assumed).
- Keypoints keep RTMPose's own scores; thresholds and class meaning are unchanged.
- An all-zero window scores about 0.20 Fall on the real model, so empty windows must
  never be passed to it; the engine only sends windows built from real poses.

## Hand-offs

- **Development:** the engine matches `api/engine.py` (`ready`, `model_version`,
  `analyze_video`, `close`). `tests/test_engine.py::ApiIntegrationTests` runs it
  inside the job runner. Real API smoke checks also completed. Reports/incidents
  stay at the API boundary.
- **Development:** poses and predictions use original-source pixels and source time;
  scale from `frame_width`/`frame_height`. A missing pose means no overlay.
- **Development:** use `tools.run_engine_clip` or the API for real outputs. Please review
  the preprocessing claim (below), the detector/gap decisions, and MMAction2 parity.
  Report processing time separately from source-timeline event delay
  ([metrics](../docs/interfaces/metrics.md)).
- **Deployment owner (Person 5):** runtime deps are in `requirements.txt` (`numpy`, `opencv-*`,
  `onnxruntime`, `rtmlib`, `psutil`; resolve the OpenCV duplicate noted in the
  [stack](../docs/project/stack.md)). On first load rtmlib downloads the YOLOX-tiny
  and RTMPose-s ONNX files (URLs in `icare_app/pose.py`) into
  `$TORCH_HOME` or `$XDG_CACHE_HOME`/`~/.cache` + `/rtmlib/hub/checkpoints`. Bake
  that cache into the image or give the host network access; otherwise `/ready`
  stays 503 with `model_unavailable`. Two PoseC3D calls on the development CPU took
  about 0.43-0.49 s each (one-off observation, not a benchmark), so a 60 s upload
  needs roughly 75 predictions of classifier time plus pose time.

## Preprocessing facts

`pose_sequence_to_heatmaps` normalises each window to a square box around all valid
joints (padding 0.25, 64x64, sigma 0.6, confidence-weighted). It is invariant to
person position and size (tested), which is why poses may be buffered in source
pixels. Parity with the MMAction2 validation pipeline on real samples has **not**
been checked; Development owns that comparison.

## Known limits and unverified items

- Real two-clip inference passed locally; broader controlled evaluation, hard
  negatives and real no-person/gap/cancellation coverage remain pending. Use
  `tools.run_engine_clip` for reproducible output with independent labels.
- Only the largest person is followed; a second person is ignored.
- Variable-frame-rate videos and rotation metadata follow OpenCV's decoding.
- Live RTMPose poses may differ from the dataset's pose generator (domain gap).
- Thresholds are unchanged (0.50 / 0.35); no calibration was done here.

## Files and tests

| File | Role |
| --- | --- |
| `engine.py` | Config, errors, frame sampling, per-clip analysis, `load_engine` |
| `engine_model.py` | Metadata/ONNX verification, classifier, pose model loading |
| `pose.py` | Detector/pose operations (`fork()` added); live worker is legacy reference |
| `posec3d_bridge.py`, `pose_signals.py` | Window/heatmaps and urgency/reliability (unchanged) |
| `../tools/run_engine_clip.py` | Real-clip runner for local evidence |
| `../tests/test_engine.py` | 43 lifecycle tests; real ONNX and API tests run when onnxruntime/fastapi are installed |

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_engine -v
```

## Rules for AI sessions touching this part

Do not route uploads through the live frame-dropping worker, recreate `app.py` or
Gradio, add LLM calls to inference, fabricate or clip probabilities, change class
order/preprocessing/thresholds without Development's validation, or import onnxruntime,
rtmlib or psutil at module level in `engine.py`/`engine_model.py` (CI's test
environment does not install them).
