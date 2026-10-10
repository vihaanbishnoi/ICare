# Development and validation

The project now has two responsibilities. Development (the project owner and
coding assistant) owns the engine, API, frontend and evaluation. The deployment
owner (Deployment owner (Person 5)) owns hosting, HTTPS, operational budgets, container verification
and the live release. There are no numbered developer roles or review handoffs.

Read [implementation status](project/implementation_status.md), the relevant
[interface](interfaces/README.md), and the component README for the task.
Extend the working Python/FastAPI/React application; keep trained weights,
class order, preprocessing and thresholds traceable to validation.

## Development completion

- Exercise real independent clips, no-person/short coverage, cancellation,
  preprocessing comparison and reproducible model/runtime versions.
- Enforce visitor admission, active-job/storage budgets, expiry and recovery.
  Keep anonymous uploads private and results derived from actual ONNX outputs.
- Verify browser loading, errors/retry, playback, seeking, cancellation, downloads,
  mobile layout, keyboard operation and accessible controls.
- Make evaluation reject unverified labels/annotations and report failures
  separately from predictions; record hardware/configuration/hash/repeat runs.
- Run available real benchmarks and retain truthful evidence of missing data.

## Inputs that cannot be invented

Historical metric reproduction needs the original dataset, split manifest and
prediction/label files. Numerical training-pipeline comparison needs the original
MMAction2 configuration/dependency versions and paired validation poses. Public
examples need their actual source and redistribution permission. Broad
hard-negative/subject-independent claims need representative labelled recordings.
Missing inputs stay explicitly pending while engineering work continues.

## Checks

From the root: `python -m tools.check_repository` and
`python -m unittest discover -s tests -v`. In frontend/: `npm test`,
`npm run build`, and `npm run lint`. Keep test adapters labelled. Test-only
requirements belong in a separate environment from the real model runtime.

For release tasks use the [deployment guide](../deployment/README.md) and
[runbook](../deployment/runbook.md). Public host measurements and credentials
belong to the deployment owner; source/runtime fixes belong to development.
