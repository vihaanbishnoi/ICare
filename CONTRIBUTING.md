# Contributing to ICare

Read the [product brief](docs/product/brief.md), [five-part ownership table](docs/team/ownership.md),
your numbered brief, and the [starter backlog](docs/team/backlog.md). The teammates
choose the parts themselves; the [roster](docs/team/roster.md) is unassigned.
Person 5 coordinates integration and release. The project owner is not a sixth
developer, maintainer, or report writer.

## Choose and begin

1. Choose five different parts and record the individuals in the ownership table.
2. Person 5 creates the shared board/issues and arranges repository/host access.
3. Use the [default stack](docs/project/stack.md), [v1 contracts](docs/interfaces/README.md),
   and your [AI starter prompt](docs/team/prompts/README.md).
4. Use one branch and draft PR per deliverable; identify it as Person 1 through 5.
5. Request review from adjacent affected parts. Person 5 tracks integration;
   each owner implements/fixes their own component.

CODEOWNERS deliberately has no active username rules until selection. Person 5
fills it after choices/access are agreed. Until then reviewers are requested manually.

## Current baseline setup

The old launcher/Gradio UI were removed. These verify the retained model/library
baseline; there is no product web startup yet:

```powershell
git clone https://github.com/vihaanbishnoi/ICare.git
cd ICare
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tools.check_repository
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On Linux/macOS use python3.11 and .venv/bin/python. Engine initialization may
download pose weights. Current checks do not prove model accuracy or deployment.
requirements-test.txt is for a separate test-only environment, not the browser app;
do not mix its headless OpenCV with the runtime dependency set.

Person 5 supplies verified product/container commands after API/frontend exist.
No Dockerfile, dependency stack, or implementation is implied by a planning folder.

## Reuse and replacement

Follow [component decisions](docs/project/component_decisions.md).
Person 1 keeps useful model operations; Person 2 rebuilds job orchestration;
Person 3 builds a fresh frontend. Nobody must preserve Gradio callbacks, global
sessions, the current upload loop, simulated preview, or timer-generated reports.

Gradio UI and launcher removal is complete. Do not restore them as a product
shortcut. Useful model operations and incident/report semantics are retained;
Person 5 coordinates any further retirement of references with their owners.
Do not erase useful model weights or evidence to make the repo look empty.

## Parallel work and review

- Person 1 and Person 2 agree inference input/output, job state, and completion.
- Person 2 and Person 3 agree media/overlay, job states, incidents, and errors.
- Person 4 defines labels, benchmarks, metric units, provenance, and missing values.
- Person 2 and Person 5 agree anonymous ownership, quotas, cleanup, and security.
- Person 5 maintains staging and integrates each part's report/docs/evidence.

Keep each PR scoped. Record whether a component is reused, refactored, replaced,
or new. Link blocking issues and affected consumers. Merge changes to shared
interfaces only with their owners' review.

Start from updated main, use a feature branch, and push a draft PR. Agent-created
branches use codex/ by default. Fetch/merge origin/main when needed and rerun
relevant checks. Avoid unrelated formatting/dependency changes in a feature PR.

## Test and evidence rules

Keep synthetic unit tests under tests/. Add actual API/browser/runtime integration
checks when those implementations exist. Development fixtures and simulated
incidents must not appear as published model results.

Private videos, raw datasets, credentials, reports, and random checkpoints stay
out of Git. Store generated outputs in ignored artifacts/; commit only approved,
sanitized evidence with provenance. Preserve metric/threshold/split meanings.

## GitHub and release coordination

Person 5 arranges the team's accepted access and configures main to require PRs,
at least one non-author approval, resolved conversations, and passing checks.
Use code-owner review once roles/access are set and the GitHub plan permits it.
The account holder may need to grant permissions; this is not a sixth workstream.

Existing checks after their first GitHub run: Repository checks,
Unit tests (ubuntu-latest), Unit tests (windows-latest), Credential scan.
Person 5 expands CI for the actual product. A green baseline unit job is not a release.

Use Backlog, Ready, In progress, In review, Done columns. Person 5 tracks the
[release criteria](docs/product/release_criteria.md) and integrates the final
README/report; the other four supply verified sections and fix their components.

GitHub reference: [code-owner access requirements](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).
