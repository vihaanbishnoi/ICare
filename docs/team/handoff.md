# ICare clean handoff start here

This is the team build plan for the supplied recruiter-ready ICare proposal.
Preparation supplies context and structure, not a finished application. Read this
page, choose one numbered part, and use that part's brief and AI starter prompt.

## Finished product

A recruiter opens a public HTTPS URL without login or local setup. They choose
Fall Example, Normal Activity, or Upload Your Video; see actual video/person/pose,
confidence over time and event state; open incident details; and explore real
results, How it works, architecture, deployment, and limitations.

Core release comes before webcam, extra safety behaviours, research novelty,
papers, or patent claims. The project is a research prototype.

## Five parts and the first useful delivery

| Part | First task | Input | Output for the next person | Completion proof |
| --- | --- | --- | --- | --- |
| [Person 1 Engine](person_1.md) | Make deterministic offline inference finish correctly | Existing model, pose/heatmap code, approved video | Actual pose/probability records and engine lifecycle for Person 2 | Final output included; job state cannot carry across clips |
| [Person 2 API](person_2.md) | Build the v1 job/API boundary with an injected engine | Engine contract, event semantics, example metadata | Owned jobs/media/results/incidents/reports for Person 3 | Two visitors isolated; failures/cancellation/completion tested |
| [Person 3 Frontend](person_3.md) | Build fall/normal/upload journeys with labelled dev fixtures | API v1 and product brief, then real example assets | Responsive website consuming the actual API | Three actions work on staging; overlays/timeline/state agree |
| [Person 4 Evidence](person_4.md) | Obtain approved examples and record evaluation gaps | Available recordings/data, metadata, model outputs | Clip/provenance manifest, measurements, plots, limits | Published numbers trace to real labels/model/configuration |
| [Person 5 Release](person_5.md) | Publish the prepared baseline and coordinate first staging slice | Chosen roles, four components, contracts, account access | Docker/startup, HTTPS live URL, runbook, final docs/report | Clean-clone startup and deployed example/upload flow verified |

All usernames stay [unassigned](roster.md) until the team chooses. Person 5 handles
coordination, integration, deployment, README, and report assembly. The other four
supply their component and report sections. No development or integration work is
assigned to the project owner.

## What exists and what to build fresh

Keep: trained ONNX model, runtime metadata, useful detection/pose/heatmap operations,
urgency/reliability instrumentation, subject audit, and selected semantic tests.
Historical classifier results are group-aware, not live-service or verified
subject-independent performance.

Removed: Gradio/FastRTC UI, root launcher, shared UI globals, upload callback loop,
and report-writing timer. They are not a starting application to repair.

Build fresh: FastAPI jobs/API/private storage and React/TypeScript/Vite frontend.
Refactor selectively: model engine offline lifecycle and completion. Do not retrain
or rewrite pretrained model families merely to reorganize the repo.

inference.py and reports.py are retained semantic references, not product
orchestration/storage. Person 2 reads event rules/field meanings but does not
wrap the old session processor or predictable filename writer as the new API.
See [component decisions](../project/component_decisions.md) for precise boundaries.

## Minimum context for each coding session

1. Read AGENTS.md (CLAUDE.md imports it for Claude Code).
2. Read your numbered brief and copy its [starter prompt](prompts/README.md).
3. Use the [default stack](../project/stack.md) and only the relevant
   [v1 contract](../interfaces/README.md).
4. Start one [backlog](backlog.md) deliverable in your branch, not the whole project.

In plain ChatGPT/Claude chat, supply the actual files. Local path names do not
give the assistant access. Do not make every session read all documentation.
Use the [AI workflow](ai_workflow.md) for context and PR handoff details.

## How the parts connect

Original video -> Person 1 engine -> Person 2 jobs/incidents/results ->
Person 3 playback/visualization. Person 4 checks data and measurements at every
boundary. Person 5 packages and deploys the same components.

Use v1 defaults immediately; a necessary change is recorded by Person 5 with
affected owners, not independently invented in five AI chats. Persons 2/3 can
use explicit development adapters/fixtures while the real engine/assets arrive.
Fixtures never become public inference evidence.

## Build order

1. Publish this handoff revision; choose parts; start approved-example procurement.
2. Build one real fall/normal example through engine, API, frontend, staging.
3. Complete short uploads, incident details, privacy/limits, and real measurements.
4. Pass [public release acceptance](../product/release_criteria.md).
5. Add optional webcam and one measured optimization only after the baseline.
6. Consider additional safety behaviours after the core product is reliable.

See [proposal coverage](../product/proposal_coverage.md): every requested outcome
has a responsible part and evidence requirement.

## Missing inputs and current runnable checks

Approved fall/normal clips, original training/split evidence where needed, host
access, and actual product implementations remain to be supplied by their owners.
Do not invent data, permissions, latency, live URLs, or novelty claims.

No web launcher exists yet. Current checks are python -m tools.check_repository
and python -m unittest discover -s tests -v. requirements-test.txt is for a separate
test-only environment. Person 5 documents actual service/container startup once built.

The latest files must be committed/pushed before cloning the old remote gives
teammates this context. The prepared handoff ZIP contains the current source and
context; Person 5 publishes the shared baseline from it or the working tree.
