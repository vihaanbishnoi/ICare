# Development workflow

Development (the owner and coding assistant) covers engine, API, frontend and
evaluation. Person 5 owns hosting and live release. Read [development](docs/development.md),
[current status](docs/project/implementation_status.md), the component README and
relevant [interface](docs/interfaces/README.md). The numbered collaboration
briefs and review handoffs are retired.

Use a focused branch/PR when sharing changes; extend working components and keep
unrelated local work intact. Update contracts and affected consumers together.
No person-to-person approval is needed to implement development fixes.

Follow [local startup](README.md#run-locally). Runtime uses root requirements.txt
plus api/requirements.txt; requirements-test.txt belongs in a separate test-only
environment. Use Node 24+ and the frontend lockfile.

Checks: python -m tools.check_repository; python -m unittest discover -s tests -v;
frontend/ npm test, npm run build, npm run lint. Report real model/browser checks
separately from labelled synthetic tests. Do not invent rights, metrics or novelty.

Keep credentials, raw datasets, private media, local caches and generated reports
out of Git. Preserve trained weights and evidence. Public release requirements
are in [release criteria](docs/product/release_criteria.md) and the
[deployment runbook](deployment/runbook.md).
