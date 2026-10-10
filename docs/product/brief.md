# Recruiter ready ICare product brief

## Objective

Deliver one polished public fall-detection research product with real outputs,
measured performance, and clear engineering explanations. It should be understandable
in 30 seconds, explorable in two minutes, and supported by deeper ML evidence.

## Essential first release

- Public HTTPS URL; no install or login for the main demo.
- Approved fall example, normal activity, and short-video upload.
- Video/person/skeleton, confidence timeline, event state, incident details/report.
- Responsive design, useful loading/errors, concise How it works.
- Real classification/deployment metrics and honest limitations.
- Simple/technical architecture explanations, strong README, reproducible startup.
- Isolated uploads/results, bounded execution, quotas, retention, and cleanup.

Cached examples are allowed when their genuine inference/configuration is
labelled. Synthetic development fixtures must not become production evidence.

## Visitor journey

Home -> Fall example or Normal activity -> watch video/confidence/state ->
open incident detail -> explore How it works and metrics. Upload is the third
primary action. Webcam comes later and must not gate the examples.

Use everyday language first; explain YOLOX/RTMPose/PoseC3D in technical views.
Do not advertise caregiver notification or emergency response as implemented
when no such integration exists.

## Next priorities and deferred scope

Measure CPU/RAM, model calls, end-to-end FPS, false alarms, and alert latency.
Test blur, occlusion, missing joints, cropping, hard negatives, and generalization
where suitable data exist. Compare one defensible optimization after the baseline.

Webcam, inactivity, restricted zones, wandering, a paper, and patent claims do
not block the example/upload release. More behaviours are lower priority than
a reliable product, real measurements, and a clear explanation.

## Existing evidence

Reported group-aware baseline: precision 97.09%, recall 94.75%, fall F1 95.90%,
balanced accuracy 96.20%, average precision 99.61%. These are not live-service
or subject-independent results. ICare remains a research prototype.

[Development](../development.md) owns implementation, evaluation and the academic
report. Person 5 owns hosting and live release.
