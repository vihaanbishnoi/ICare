# Person 1 Inference engine and model runtime

## Outcome and boundary

Deliver an actual pose-based temporal engine that reliably finishes a clip and
exposes useful measurements. Own icare_app/pose.py, onnx_backend.py,
posec3d_bridge.py, pose_signals.py, and model/runtime metadata. Person 2 owns
jobs/incidents; Person 4 reviews model and preprocessing claims.

## First steps

1. Read [component decisions](../project/component_decisions.md) and the model metadata.
2. Verify real model loading, class order, timestamp units, and preprocessing.
3. Agree the [inference boundary](../interfaces/inference.md) with Person 2.
4. Deliver deterministic offline sampling and explicit final-output completion.

Use the [Person 1 starter prompt](prompts/person_1.md) and
[default stack](../project/stack.md) for an AI coding session.

## Reuse or rebuild

Keep trained weights and useful detector/pose/heatmap operations. Refactor the
live worker/mutable buffer coupling. Build an offline path fresh if the latest-frame
worker would discard selected poses. Do not reimplement existing model families
just to reorganize folders.

Urgency/reliability are instrumentation initially. Adaptive scheduling is a later
measured experiment, not a first-release requirement.

## Deliverables and acceptance

- Reusable engine/lifecycle separate from HTTP and browser callbacks.
- Accurate pose, timestamp, probability, and measured inference records.
- Readiness/error handling and documented preprocessing.
- Tests for completion, reset, no person, and independent consumers.
- Runtime architecture/temporal reasoning content for Person 5's report assembly.

Done when Person 2 can run two independent jobs without mixed pose/results and
Person 4 can benchmark real outputs. Final inference arrives before completion;
model failure cannot appear as fabricated confidence.

Review with Persons 2 and 4; provide packaging requirements to Person 5.
