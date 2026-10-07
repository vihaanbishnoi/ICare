# Starting with ChatGPT Codex or Claude

## One entry point for each teammate

Choose one numbered part, clone/open the shared handoff revision, and use that
part's [starter prompt](prompts/README.md). Work on one deliverable in a branch.
Person 5 coordinates integration; there is no separate project-owner coding role.

Repository-aware coding tools can inspect the clone. Codex uses AGENTS.md project
instructions; CLAUDE.md imports that same file for Claude Code. See
[OpenAI's AGENTS guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
and [Claude project instructions](https://code.claude.com/docs/en/memory).
These instructions guide behavior, not a technical boundary preventing edits.

If using plain browser ChatGPT/Claude, attach or provide AGENTS.md, your numbered
brief, stack.md, relevant v1 contracts, and relevant source files. Pasting a local
path is not proof that a chat can read it. The prompt requires the assistant to
identify unavailable context before writing code.

## Minimum role context

| Part | Read for the first deliverable | First useful result |
| --- | --- | --- |
| Person 1 | person_1.md, inference.md, model metadata and engine source | Real offline engine completion, without GUI |
| Person 2 | person_2.md, api.md, inference.md, incident/report reference | Typed API/job boundary with injected engine adapter |
| Person 3 | person_3.md, api.md, product brief, stack.md | Responsive example/upload journey against labelled dev fixtures |
| Person 4 | person_4.md, metrics.md, dataset/evaluation status | Approved examples/provenance and repeatable baseline protocol |
| Person 5 | person_5.md, stack/contracts, CI and runbook | Shared baseline/role selection and one staging integration plan |

Read additional files only when the task needs them. Do not ask every AI session
to ingest the full project or rebuild all five components.

## Work independently without inventing dependencies

The v1 defaults let Persons 2/3 start with explicit development adapters/fixtures
while Person 1 implements real processing. Person 4 starts data/example work
immediately. Person 5 starts access, packaging plans, and integration in parallel.
Unavailable hardware/data/host access must be reported, not replaced with fake results.

One human chooses a part; that human and their coding assistant own its PR.
AI-generated output needs actual tests and review from affected parts. Prompts do
not grant permission to edit others' work or publish credentials/private media.

## Required handoff from each coding session

- Deliverable implemented and files changed.
- Exact commands run and outcomes; what was not exercised.
- Contract version and any coordinated interface changes.
- Model/data/configuration evidence where results are claimed.
- One next dependency or integration action for the adjacent part.

Keep this in the PR/issue, not in a second conflicting architecture document.

## Getting this handoff to the team

These changes must be committed/pushed before teammates cloning the existing
remote can use them. Person 5 handles that baseline once they have the working
tree or handoff snapshot and accepted access. Check that AGENTS.md, numbered
briefs, contracts, models, and CI are present on the shared revision.

The legacy app.py/ui.py and their Gradio/FastRTC dependencies were removed. A
local ignored backup exists only on the preparation machine. Start new API/UI
components; do not spend time repairing the retired demo.
