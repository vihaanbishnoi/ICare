# Person 2 API jobs incidents and private results

## Outcome and boundary

Build api/ for approved examples, short uploads, job progress, actual results,
incidents, and private reports. Own adaptation of icare_app/inference.py
session/incident logic and reports.py. Person 1 provides computation and
Person 3 renders API data.

## First steps

1. Agree the [API boundary](../interfaces/api.md) with Person 3.
2. Agree [inference completion](../interfaces/inference.md) with Person 1.
3. Build isolated jobs fresh rather than inheriting Gradio globals.
4. Ship one example end to end, then add uploads and limits with Person 5.

Use the [Person 2 starter prompt](prompts/person_2.md) and
[default stack](../project/stack.md). API defaults are FastAPI under /api/v1;
do not let an independent AI session invent a different backend protocol.

## Reuse or rebuild

Keep valid incident thresholds/deduplication and report field meanings. Replace
shared globals, reset coupling, reused report paths, the old upload loop, and the
one-second report-writing timer. Preserve no legacy callback interface by default.

Read only the useful reference semantics: ModelOutput/FallEvent fields,
_consume_output threshold/rearm behavior, and EVENT_FIELDS/INFERENCE_FIELDS.
Do not port FallDetectionSession.process(), its frame overlay/demo injection,
or write_report() filesystem strategy into the new service. Build those boundaries
fresh in api/ so the AI task cannot accidentally inherit retired orchestration.

The website requires no account login. Browser/job ownership still protects
uploads and results; random filenames alone are not authorization.

## Deliverables and acceptance

- Example catalogue, job creation/status/results, incident details, cancellation,
  and session-owned downloads.
- Bounded execution, unique storage, cleanup, and clear validation/model errors.
- Format/bytes/duration/rate/concurrency limits with Person 5.
- Integration tests for two visitors, same-named uploads, final completion,
  cancellation, and unauthorized downloads.
- Incident lifecycle, finalized API contract, and report content.

Done when Person 3 uses the API without model imports, jobs cannot reset/overwrite
one another, completed results contain final real inference, and anonymous-demo
access does not expose private uploads. Review with Persons 1, 3, and 5.
