# AGENTS.md

## Project overview
MarketAnalyzer is a local personal investing workstation with a Python backend and a Vue frontend. It combines watchlist signals, chart analysis, and a lightweight portfolio tracker.

- **Backend**: Flask app under `backend/`
- **Frontend**: Vue 3 + Vite under `frontend/`
- **Data**: Cached under `backend/data/`

## Architecture (high-level)
- **Pages**
  - `Home` → daily overview + watchlist snapshot
  - `Analyze` → charting + indicators + drawings + signal overlays
  - `Portfolio` → auto-price BUY flow + positions + equity curve
  - `Simulation` → placeholder for what‑if scenarios
- **Backend endpoints**
  - `GET /api/assets` → returns full list (cached history, resampled) + usage stats
  - `GET /api/asset?symbol=...&type=...&interval=...&chart_points=...&refresh=1` → refreshes a single asset
  - `GET /api/watchlist` / `POST /api/watchlist` / `DELETE /api/watchlist/<symbol>`
- **Data providers**
  - **Stooq** for daily candles (primary, cached)
  - **Alpha Vantage** daily adjusted (fallback, quota-limited)
  - **FRED** for commodity series

## Key files
- Backend
  - `backend/app/dashboard.py` – Flask routes + payload shaping
  - `backend/app/asset_manager.py` – provider selection, cache TTLs, fallback logic
  - `backend/app/asset_cache.py` – asset cache persistence (`backend/data/asset_cache.json`)
  - `backend/app/usage.py` – quota tracking + cache hit stats (`backend/data/usage.json`)
  - `backend/app/providers.py` – Stooq/Alpha fetch + resampling + currency inference
  - `backend/app/analysis.py` – feature calculation & scoring (30D / 3M)
  - `backend/app/watchlist.py` – watchlist persistence (`backend/data/watchlist.json`)
- Frontend
  - `frontend/src/App.vue` – app shell + tabs
  - `frontend/src/router/index.js` – Home / Analyze / Portfolio / Simulation routes
  - `frontend/src/composables/useAssets.js` – API calls + cache merge + usage stats
  - `frontend/src/components/panels/ChartPanel.vue` – chart UI (fullscreen, indicators, drawings)
  - `frontend/src/chart/` – chart core + indicators + drawings + local storage
  - `frontend/src/components/panels/SignalsPanel.vue` – signals list + mapping UX
  - `frontend/src/pages/Portfolio.vue` – auto-price BUY flow + positions + transactions
  - `frontend/src/stores/portfolio.js` – WAC positions + equity curve
  - `frontend/src/stores/settings.js` – fee policy + quantity precision
  - `frontend/src/style.css` – global UI theme

## Running locally
- **One command (dev)**
  ```bash
  cd frontend
  npm install
  npm run dev
  ```
  This runs both Vite and Flask.

- **Backend only**
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -r backend/requirements.txt
  cp .env.example .env
  python backend/run.py
  ```

## Important behaviors
- **Free-tier safe**: no auto polling; only refreshes when user clicks “Refresh now”.
- **Daily history** uses Stooq cache (multi-year). Weekly/monthly are resampled locally.
- **Manual refresh** updates only the selected asset and respects Alpha budgets.
- **Portfolio** data lives in IndexedDB (transactions) with derived positions + equity curve.

## Common gotchas
- Alpha Vantage free tier limits are strict (25 req/day). Refresh sparingly.
- Stooq is unofficial and can fail; cached data is used when refresh fails.
- If charts are blank, ensure data exists in `backend/data/cache/` and restart both servers.
 - Portfolio history is stored in IndexedDB; clearing site data will wipe it.

## Next steps / expansion ideas
- Add symbol search endpoint (if provider supports it)
- Add what‑if simulation tools + scenario persistence
- Add portfolio imports (CSV) + export
