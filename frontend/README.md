# ICare React Frontend

React + TypeScript + Vite implementation of the ICare fall-detection demo UI.

## Stack

- **React 19 + TypeScript 6** — component framework
- **Vite 8** — build tool and dev server
- **Vanilla CSS** — ported from approved `frontend/style.css` design (GitHub dark palette)

## Development

```bash
# From this directory:
npm ci
npm run dev        # http://localhost:5173  (proxies /api/v1 → http://127.0.0.1:8000)
```

The backend must be running for inference to work. Start it with:

```bash
# From the repo root:
uvicorn api.main:create_app --factory --port 8000
```

The Vite dev proxy forwards all `/api/v1/*` requests to the backend so the
browser sees one origin. It preserves Host for API origin validation; override
the target with `ICARE_API_TARGET` when using another backend port.
Use Node 24 or newer for the built-in TypeScript regression test runner.

## Same-origin requirement

All API calls use **relative URLs only** (`/api/v1/…`). Do NOT introduce absolute
URLs — the backend session cookie is `SameSite=strict; HttpOnly` and will be
blocked if the request origin doesn't match.

In production, Deployment owner (Person 5) configures the reverse proxy to serve both the built
frontend and the FastAPI backend from the same HTTPS origin.

## Source layout

```
src/
  api/client.ts          # Typed fetch calls for all /api/v1 endpoints
  hooks/useJobPoller.ts  # Polls a job until terminal state (~1 s interval)
  components/
    VideoPlayer.tsx       # <video> + <canvas> pose overlay (COCO-17 keypoints)
    ConfidenceChart.tsx   # SVG timeline from real predictions[]
    ResultsPanel.tsx      # Chart + incidents + summary + report downloads
    ExamplePanel.tsx      # Loads examples from API, starts jobs, shows results
    UploadPanel.tsx       # Real multipart upload, job polling, results
  types.ts               # Mirrors api/schemas.py (Prediction, Pose, Result, …)
  App.tsx                # Full page: Nav, Hero, Demo, How It Works, Metrics, Footer
  App.css                # Approved GitHub dark design system
```

## API calls implemented

| Endpoint | Used by |
|---|---|
| `GET /api/v1/examples` | ExamplePanel — loads approved clips |
| `POST /api/v1/jobs/example` | ExamplePanel — starts example inference |
| `POST /api/v1/jobs/upload` | UploadPanel — real multipart upload |
| `GET /api/v1/jobs/{id}` | useJobPoller — ~1 s polling |
| `GET /api/v1/jobs/{id}/results` | ResultsPanel — gets Result document |

## What was fixed (per rework brief)

- **No Math.random() / fake upload progress** — real `FormData` POST, real poll
- **Real `<video>` element** — `media_url` from Result document
- **Canvas pose overlay** — `poses[].keypoints` (COCO-17) + `bbox_xyxy` scaled
  from `frame_width/frame_height` to displayed pixel dimensions
- **Confidence chart** — from real `predictions[].fall_probability`
- **Incident list** — from real `incidents[].detected_at_seconds/confidence`
- **"12 FPS / stale frames"** → fixed to "Frame Sampling ~6 poses/source-second"
- **Meta description** — removed inaccurate "Watch real skeleton tracking"
- **Same-origin URLs** — all API calls are relative; Vite proxy for dev

## Playback and failure handling

This app displays real API records. Confidence uses the latest prediction at or
before playback time, clears stale records, and never reads future predictions.
Pose gaps clear the overlay. Recorded incidents do not imply a fabricated
four-second recovery. Hero and demo tabs share selection state. Polling surfaces
permanent errors and stops after three consecutive transient failures; status
retry resumes the same job. Synthetic adapters remain test-only.

Local browser checks completed a fall example and normal-video upload. DOM journey tests cover completion, seeking, retry, cancellation and upload errors.
Broader mobile/accessibility/browser checks remain further validation.

## Build

```bash
npm run build    # produces dist/ — served by Deployment owner (Person 5) from /
npm test         # four playback tests and eight DOM journey regressions
npm run lint     # clean
```
