# Person 3 — Public Frontend

**Status: P3A fixture slice complete. Pending API connection from Person 2.**

Person 3 builds the public no-login recruiter demo in this directory.
Read [Person 3 brief](../docs/team/person_3.md), [API v1 contract](../docs/interfaces/api.md),
[stack](../docs/project/stack.md), [product brief](../docs/product/brief.md),
and the [starter prompt](../docs/team/prompts/person_3.md) before modifying.

---

## What is implemented

This PR delivers the first frontend fixture slice (P3A). Three files were added:

| File | Purpose |
|---|---|
| `index.html` | Full semantic HTML5 single-page app |
| `style.css` | GitHub dark theme design system (CSS custom properties, glassmorphism, responsive) |
| `app.js` | Hero particle animation, skeleton renderer, SVG confidence chart, tab switching, upload stub |

### Sections built

- **Navigation** — sticky with mobile hamburger, scroll shadow
- **Hero** — animated particle-network canvas, gradient title, 4 performance stat cards, CTA buttons
- **Demo** — three tabs:
  - *Fall Example* — animated stick-figure skeleton (walk → fall → ground), SVG confidence timeline with playhead synced to animation, incident panel with FALL DETECTED alert
  - *Normal Activity* — walking figure, flat confidence timeline below threshold, empty incident state
  - *Upload Video* — drag-and-drop MP4 zone, limits list (50 MB / 60 s / MP4 / 24 h retention), privacy notice, graceful 503 stub when backend is absent
- **How It Works** — five-stage pipeline diagram with icons and hover lift
- **Performance Metrics** — six animated stat cards + confusion matrix table (TN/FP/FN/TP from README)
- **Limitations** — six honest limitation cards
- **Footer** — links, fixture notice

### Design

- Colour palette: GitHub dark theme (`#0d1117`, `#161b22`, `#21262d`, `#30363d`, `#58a6ff`, `#3fb950`, `#f85149`)
- Typography: Inter (body) + JetBrains Mono (code/timestamps)
- Fully responsive: 1-column layout on mobile, grid on desktop

---

## Development fixtures

All mock data is in `app.js` under the `FIXTURES` constant and is clearly labelled
`DEVELOPMENT FIXTURE — not real inference` in the UI and in code comments.

**Fixtures must be replaced with genuine `/api/v1` responses before public release.**
Do not publish fixture confidence values or incident timestamps as model evidence.

---

## API client contract

The frontend is written against the `/api/v1` contract in [`docs/interfaces/api.md`](../docs/interfaces/api.md).
No routes, field names, or coordinate conventions were changed.

Endpoints consumed:
- `GET /api/v1/examples` — example catalogue (currently fixture-mocked)
- `POST /api/v1/jobs/example` — run example job (stub)
- `POST /api/v1/jobs/upload` — upload job (stub, returns 503 when not connected)
- `GET /api/v1/jobs/{job_id}` — poll job state (stub)
- `GET /api/v1/jobs/{job_id}/results` — completed result (stub)

---

## What still needs to happen (integration dependencies)

| Item | Blocked by |
|---|---|
| Real video playback + actual COCO-17 pose overlay | **Person 4** — approved labelled clips needed |
| Genuine inference results replacing fixtures | **Person 2** — `/api/v1` backend not yet deployed |
| Upload running real inference | **Person 2** — `/api/v1/jobs/upload` not yet wired |
| Metrics text confirmed from real evaluation | **Person 4** — evidence audit not yet complete |
| HTTPS public URL verification | **Person 5** — staging not yet deployed |
| Browser interaction / E2E tests | Person 3 — to be added once API is live |
| Walkthrough screenshots for combined report | Person 3 — to be added at integration stage |

---

## Changed files

```
frontend/README.md      ← this file (updated)
frontend/index.html     ← new: full HTML page
frontend/style.css      ← new: GitHub dark design system
frontend/app.js         ← new: animations, chart, tab switching, upload stub
```

Files outside `frontend/` were not modified.

---

## How to run locally

Open `frontend/index.html` directly in a browser (no build step, no server needed for fixtures).
Once Person 2's API is running, point `app.js` API calls to `http://localhost:PORT/api/v1`.
