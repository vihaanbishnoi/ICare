# Implementation and release status

Verified locally on 10 October 2026. Development owns the engine, API, frontend,
evaluation and report. Person 5 owns deployment. The retired numbered role
briefs, prompts, roster and handoff have been removed.

## Completed development

- CPU pose/ONNX engine with independent clip state, source timestamps and final output.
- Isolated spawned model process; cancellation terminates stuck native calls,
  crashes recover, and queued work waits for model reload.
- FastAPI owned jobs/media/results/JSON/CSV, streaming MP4 validation, finite
  output validation, no-store responses, expiry and crash reconciliation.
- Atomic visitor/network admission, two active jobs per visitor, twelve requests
  per visitor/hour and sixty per network/hour by default; five queued globally.
- Job-file storage reservations default to 1 GB globally and 5 MB per result;
  oversized result documents fail before writing. Upload limit remains 50 MB / 60 s.
- React video/pose/confidence/incident views, source-time seeking, status/result
  retry, cancellation and stale-response protection. Lint is clean.
- Evaluation distinguishes failures/unverified labels from successful predictions;
  false-alarm rates use verified normal exposure. Manifest path handling is fixed.
- Completed 14-page [academic report](ICare_Report.docx) with [editable source](report.md),
  actual execution traces/features/resources and five analysis pages.

## Verification

| Check | Outcome |
| --- | --- |
| Python clean environment | 108 tests: 104 passed, four optional ONNX tests skipped |
| Frontend | Four playback and eight DOM journey tests passed; production build/lint passed |
| Actual isolated CPU model/API | Two six-second clips completed; six predictions/one incident and four predictions/no incident |
| Model resources | 22.515 / 16.922 seconds; sampled RSS peaks 460.266 / 433.527 MB; single local executions |
| Privacy | Independent visitor 404, owned range media and JSON report checks passed |
| Gaussian kernel audit | Four numeric cases against pinned MMAction2 v1.2.0 source; maximum absolute delta 0.003454; full pipeline parity not established |
| Report | 14 pages; intro 2, architecture 2, dataset 1, results/analysis 5; rendered and visually checked |
| Compose | Built and run locally 10 Oct 2026; examples, upload, isolation, cancellation, restart and smoke test pass through nginx; CI job added |

## Scientific inputs still missing

The owner identified [Kaggle payutch Fall Video Dataset](https://www.kaggle.com/datasets/payutch/fall-video-dataset).
Exact split/prediction artifacts are still needed to reproduce historical metrics.
Verified subjects, representative hard negatives and independent onset labels
are still needed for generalization, false alarms/hour and event-delay estimates.
The numerical audit identifies a real kernel difference; model preprocessing and
weights were preserved until paired validation justifies a change.

Existing diagnostic clips have unverified source/rights/labels. Unsupported
UR-dataset/CC-BY/onset claims were removed. Public example exposure defaults off
for such clips; ICARE_ALLOW_UNVERIFIED_EXAMPLES=1 is for local diagnostics only.
The two-clip report does not establish new accuracy or external superiority.

## Person 5 next

Containers are verified locally (single OpenCV, baked pose weights). Next: choose
provider/cost budgets, configure HTTPS and secure cookies, forward trusted client
address/Host/protocol, tune admission/resource budgets, test recovery/rollback,
verify permitted public example assets and publish the live URL. See the
[runbook](../../deployment/runbook.md). Mobile/manual browser breadth and broader
real-data research remain future validation, not implied by unit-test success.
