# TEOT — Connected interactive prototype

This version preserves the uploaded backend model and data scripts, and adds a **standalone Python HTTP API** (`backend/api/server.py`) plus a React dashboard that fetches it through the Vite proxy.

## Run locally (two terminals)

From the `TEOT` directory:

**Terminal 1 — Python API (standard library, no extra packages)**

```bash
python3 backend/api/server.py
```

The API listens at `http://127.0.0.1:8000/api/overview` and `/api/health`.

**Terminal 2 — React**

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (normally `http://localhost:5173`). If you have an old Vite process running, restart it so the updated proxy config takes effect.

## What works

- Frontend requests live JSON from the running Python server; loading and API-error states.
- Interactive map with hover, keyboard selection, and click-to-select; state dropdown.
- State forecast card, polling chart, and uncertainty chart synchronized to state selection.
- Date slider filters chart history and changes displayed forecast margin/interval.
- National seat distribution tab.
- Responsive CSS and animated transitions via the already-installed `motion` package (`motion/react`); reduced-motion support.

## Critical data integrity note

The supplied forecasting code does **not** currently provide a complete, runnable, calibrated model-to-HTTP pipeline. By default, the API therefore generates **synthetic data** for UI development, labeled as such on the dashboard. It does not query the database or run PyMC. The national synthetic histogram is independent of the example state probabilities and should not be interpreted as a coherent election simulation. The date slider does not provide historical win probabilities, so that value remains the illustrative latest value. Some example states do not represent actual 2026 Senate races.

To feed model-produced data without editing existing model code, set `TEOT_FORECAST_JSON=/absolute/path/to/snapshot.json` before starting the API. The snapshot must match the `/api/overview` response schema: `source`, `as_of`, `dates`, `races` (with fields from `StateForecastCard` and `polling` and `history` arrays), and `national.seat_distribution`. This is an integration seam, **not** a claim that the existing `forcast.py` output already matches the schema. A production adapter still needs to validate and transform actual forecast output, including calibrated uncertainty, archived historical snapshots, caucus alignment and holdover seats.

## Checks performed

- `python -m py_compile backend/api/server.py` succeeded.
- `tsc -b` succeeded on the uploaded dependency tree.
- Both `/api/health` and `/api/overview` returned valid JSON from a running local Python process.
- A complete Vite production bundle could **not** be tested in this Linux environment because the uploaded `node_modules` contains macOS native packages rather than the Linux Rolldown binding. Running `npm install` on your Mac installs the matching native package.

## Project changes

Added: `backend/api/server.py`, `frontend/src/services/api.ts`, `frontend/src/pages/Overview.css`, this README.

Updated: `frontend/src/pages/Overview.tsx`, `frontend/src/components/SenateMap.tsx`, `frontend/src/components/SenateMap.css`, `frontend/src/index.css`, `frontend/vite.config.ts`.

Other backend model and data scripts were not changed.
