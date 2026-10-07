# Measurement and evidence contract

Person 4 owns definitions/provenance; Persons 1 and 2 emit data. Person 3 renders
approved results and Person 5 publishes evidence.

| Metric | Required evidence |
| --- | --- |
| Precision recall F1 balanced accuracy average precision | Labels, split, threshold, classifier output |
| False alarms per camera-hour | False incidents / observed hours, with annotations |
| Median and p95 alert latency | Alert minus annotated onset; event count/percentile method |
| End-to-end FPS | Defined processed-frame count / actual processing interval |
| Model calls per minute | Actual classifier calls / observed interval |
| CPU/RAM | Process/system scope, units, provider, sampling |
| GPU usage | Actual GPU provider/run or not applicable |
| Optimization gain | Matched data/hardware/threshold/configuration comparison |

Captured FPS is not processed FPS. Inference milliseconds are not alert latency.
Sample-level false positives are not a camera-hour rate. Cached playback is not
a runtime benchmark.

For offline uploaded clips, alert timestamp minus annotated onset measures event
delay in the source video timeline. Report job turnaround/processing wall time
separately. Do not present source event delay or cached replay as measured live
end-to-end delivery latency. State the timeline used for every latency result.

Publish clip/dataset IDs and rights, split/subject status, checkpoint, preprocessing,
commit, hardware/provider, duration, labels/onset, and reproducible procedure.
Private raw recordings stay outside Git.

Missing onset means unknown latency. Unused GPU is not applicable. Planned work
is pending, never zero or an invented improvement. Existing precision 97.09%,
recall 94.75%, F1 95.90% describe the reported group-aware classifier test, not
deployed service or confirmed subject-independent performance.
