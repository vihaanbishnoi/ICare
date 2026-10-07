# Person 3 copyable starter prompt

I chose Person 3 for ICare. Read AGENTS.md, docs/team/person_3.md,
docs/product/brief.md, docs/project/stack.md, and docs/interfaces/api.md.
If you cannot access them, identify missing context before writing code.

Implement P3A/P3B's first frontend slice in frontend/ using React, TypeScript,
Vite, and one npm lockfile. Build a polished responsive fall/normal/upload journey,
video/pose overlay, confidence timeline, event state, and incident detail.
Use the /api/v1 client contract; do not invent alternative paths/fields.

Development fixtures are allowed but must be clearly labelled and gated from the
published real-inference path. Use source-frame coordinates and source-relative
time. Unknown confidence is not zero; do not fabricate model results, example
rights, benchmark values, or caregiver notifications.

Work only in frontend/ and frontend tests/docs. Do not recreate Gradio, write
Python inference, add an account-login gate, or make webcam a prerequisite.
Run type/build and meaningful browser checks as available. Report changed files,
actual validation, fixture status, and what Person 2/4/5 must supply for integration.
