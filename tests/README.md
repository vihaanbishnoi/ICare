# Tests and verification by numbered part

Current baseline: python -m unittest discover -s tests -v from the root.
Use full requirements.txt or requirements-test.txt in a separate test-only
environment. Nine existing synthetic tests are retained unchanged.

| Existing test | Relevant part |
| --- | --- |
| test_inference_logging.py | Development with Development lifecycle input |
| test_pose_signals.py | Development |
| test_subject_audit.py | Development |
| test_reports.py | Development |
| test_engine.py | Development (engine lifecycle; also runs the engine inside the API) |

Development added engine/lifecycle/completion checks (synthetic adapters; real-ONNX cases skip without onnxruntime). Development adds job/isolation/
ownership/incident/API integration checks. Development adds browser journeys/loading/
errors/mobile checks. Development verifies real-model metrics and robustness.
Deployment owner (Person 5) connects these to CI/staging and validates restart/rollback/limits.

Existing CI discovers root Python test files; new framework/directory discovery
must be deliberately configured by Deployment owner (Person 5). A new test folder alone is not wired
into CI. Critical inference/API tests are first-release requirements.

Use synthetic fixtures where meaningful, but never confuse them with measured
model accuracy or runtime benchmarks. Private data remain outside Git; real-model
and browser/network tests document their environment and sample requirements.
