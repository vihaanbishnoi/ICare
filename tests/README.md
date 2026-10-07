# Tests and verification by numbered part

Current baseline: python -m unittest discover -s tests -v from the root.
Use full requirements.txt or requirements-test.txt in a separate test-only
environment. Nine existing synthetic tests are retained unchanged.

| Existing test | Relevant part |
| --- | --- |
| test_inference_logging.py | Person 2 with Person 1 lifecycle input |
| test_pose_signals.py | Persons 1 and 4 |
| test_subject_audit.py | Person 4 |
| test_reports.py | Person 2 |

Person 1 adds engine/lifecycle/completion checks. Person 2 adds job/isolation/
ownership/incident/API integration checks. Person 3 adds browser journeys/loading/
errors/mobile checks. Person 4 verifies real-model metrics and robustness.
Person 5 connects these to CI/staging and validates restart/rollback/limits.

Existing CI discovers root Python test files; new framework/directory discovery
must be deliberately configured by Person 5. A new test folder alone is not wired
into CI. Critical inference/API tests are first-release requirements.

Use synthetic fixtures where meaningful, but never confuse them with measured
model accuracy or runtime benchmarks. Private data remain outside Git; real-model
and browser/network tests document their environment and sample requirements.
