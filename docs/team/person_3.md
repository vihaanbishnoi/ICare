# Person 3 Public frontend and demo experience

## Outcome and boundary

Build frontend/ so a recruiter opens one URL, understands the project quickly,
and watches a fall/normal example or uploads a short clip without login.
Own responsive design, playback, overlays, confidence timeline, incident details,
loading/errors, and accessible interactions.

## First steps

1. Read the [product brief](../product/brief.md).
2. Agree the [API boundary](../interfaces/api.md) with Person 2.
3. Develop against labelled fixtures while the backend is being built.
4. Replace fixtures with genuine API outputs before public release.

Use the [Person 3 starter prompt](prompts/person_3.md) and
[default stack](../project/stack.md): React/TypeScript/Vite consuming /api/v1.

## Reuse or rebuild

Start fresh; the old Gradio UI was removed to avoid conflicting implementations.
Browser code must not own model inference, deployment
keys, arbitrary server paths, or report authorization.

Cached example analysis is acceptable if labelled with its model/configuration.
Never animate invented confidence as model output or publish simulated incidents
as actual detections.

## Deliverables and acceptance

- Clean responsive home and fall/normal/upload actions.
- Video/person/skeleton, confidence timeline, event state, incident details.
- How it works and approved metrics/limitations views from Person 4's evidence.
- Empty/loading/error states and browser interaction checks.
- Walkthrough/screenshots/presentation material for Person 5.

Done when both examples and a permitted upload work on the actual live API,
mobile layout is usable, failures are understandable, and planned features are
clearly labelled. Webcam permission must not block the primary examples.

Webcam is a later bonus. Review API with Person 2, metric claims with Person 4,
and hosting behavior with Person 5.
