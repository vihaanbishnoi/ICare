# API contract version 1

Implementation owner Person 2; consumer Person 3; deployment/privacy reviewer
Person 5. Use FastAPI, prefix /api/v1, JSON snake_case fields, and seconds for
source-relative time. This contract is the starting default; it is not implemented.

## Routes and transport

| Route under /api/v1 | Input or response |
| --- | --- |
| GET /examples | examples array; empty when no approved assets exist |
| POST /jobs/example | JSON example_id; 202 Job document |
| POST /jobs/upload | multipart video field named file; 202 Job document |
| GET /jobs/{job_id} | Job document |
| GET /jobs/{job_id}/results | completed owned Result; 409 if not complete |
| GET /jobs/{job_id}/media | owned original playable video, with range support |
| GET /jobs/{job_id}/incidents/{incident_id} | owned Incident document |
| GET /jobs/{job_id}/reports/{format} | owned json or csv download |
| DELETE /jobs/{job_id} | cancel/delete owned work according to retention |
| GET /health | process liveness |
| GET /ready | actual model readiness; 503 when no real engine is ready |

Poll job state initially; no websocket/SSE requirement for the first slice.
The frontend should poll approximately once per second and stop on terminal states.
Return no server filesystem paths to the browser.

## Example document

example_id string, title string, expected_outcome fall/no_fall,
video_url public approved media URL, duration_seconds number,
analysis_mode cached/on_demand, model_version string or null,
provenance human-readable permission/source description.
Cached results must come from actual analysis and retain their version.

## Job document

| Field | Type and rule |
| --- | --- |
| job_id | opaque string |
| state | queued/running/completed/failed/cancelled |
| progress | number in [0,1] or null when unknown; 1 only after final results are written |
| source_kind | example/upload |
| created_at_utc | ISO 8601 UTC |
| model_version | verified version string or null before readiness |
| result_url | owned API URL or null until completion |
| error | null or object with code and message |

Successful POSTs return immediately with a queued/running job. Missing engine
readiness returns 503 rather than running a fake worker. The implementation
must not promise precise progress if it cannot measure it.

## Result document

job_id, duration_seconds, frame_width, frame_height, model_version,
analysis_mode, media_url, predictions array, poses array, incidents array,
metrics object, and reports object with owned json/csv URLs.
Missing optional metrics use null, not invented zero.

Prediction: timestamp_seconds, fall_probability in [0,1],
window_start_seconds, source_pose_count, inference_ms, optional urgency/reliability.
Pose: timestamp_seconds, bbox_xyxy array of four pixel coordinates, and
keypoints array of 17 [x,y,confidence] entries in COCO order.
Coordinates reference frame_width/frame_height of the original source video.
The frontend scales from those dimensions to displayed video content.

Synchronize playback to source-relative timestamps. Missing poses have no overlay;
they do not inherit another person's/job's keypoints. Person 4's labels remain
separate from predictions.

## Incident document

incident_id string, job_id string, detected_at_seconds number,
confidence number in [0,1], status detected/acknowledged,
created_at_utc string. First release defaults to detected; acknowledgement can be
added with a coordinated endpoint. Never infer safe/recovered from a lower later
probability. Report onset/latency only with valid independent annotations.

## Anonymous browser ownership

No account login gate. Person 2 establishes an opaque random browser session in
an HttpOnly cookie, with SameSite restrictions and Secure on public HTTPS.
Persist a server-side owner reference for each job and verify it on every owned
status/media/result/report/cancellation request. Public examples are not private uploads.

Use same-origin deployment. Validate mutating request origins and ownership;
random job IDs alone are not authorization. Person 5 verifies proxy/cookie behavior.
Do not expose private uploaded media as static frontend assets.

## Errors and initial limits

Error body: error object with code and readable message. Use 400 for invalid
input, 404 for unknown/not-owned resources, 409 for incomplete state,
413 for exceeded size limits, 429 for capacity/rate limits, and 503 for model unavailable.

Initial defaults to implement and measure: MP4 upload only; 50 MB; 60 seconds;
one active inference job; at most five queued jobs; ten-minute execution timeout;
24-hour maximum upload/result retention. Validate content, not only extension.
Persons 2/5 may tighten documented limits after the first host measurement;
frontend labels and tests must match the server's actual limits.
