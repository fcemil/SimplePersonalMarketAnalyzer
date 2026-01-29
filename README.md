# Market Analyzer

Local personal investing workstation with a Flask backend and Vue 3 frontend. It combines daily market signals, chart analysis, and a lightweight portfolio tracker with automatic price lookup.

Core pages:
- **Home**: daily snapshot + watchlist signals, provider freshness, and quota status
- **Analyze**: interactive charting with indicators, drawings, and signal overlays
- **Portfolio**: fast “3-field BUY” flow (symbol + date + money spent) with auto price/qty + WAC positions
- **Simulation**: placeholder for what‑if scenarios

## Fresh machine setup (macOS / Linux)

```bash
git clone <your-repo>
cd MarketAnalyzer/frontend
npm install
npm run dev
```

That will:
- create a Python virtualenv in `../.venv`
- install backend deps from `backend/requirements.txt`
- start Flask + Vite together

Open:
- Frontend: http://127.0.0.1:5173
- Backend: http://127.0.0.1:5000

## Highlights

- **Data providers**: Stooq daily candles (primary), Alpha Vantage fallback (quota-limited), FRED commodities
- **Caching**: daily refresh with provider-specific TTLs, cache hit metrics, and stale fallback
- **Signals**: 30‑day return, 30‑day volatility, 3‑month drawdown, MA20 slope with explainable contributions
- **Charts**: lightweight-charts with SMA/EMA/BB overlays + RSI/MACD/Volume panels and drawing tools
- **Portfolio**: auto fee calculation, auto quantity, WAC cost basis, and equity curve

## AI usage note

Development of this project used AI assistance for planning, coding, and refactoring.

## Backend (Flask) only

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
python backend/run.py
```

## Frontend (Vue) only

```bash
cd frontend
npm install
npm run dev
```

The frontend expects an `/api/assets` endpoint from Flask and proxies through Vite during dev.

## Customize

- Universe list: `backend/app/config.py`
- Scoring rules: `backend/app/analysis.py`
- Provider budgets + refresh rules: `backend/app/usage.py`, `backend/app/asset_manager.py`
- Frontend settings (fees, precision): `frontend/src/stores/settings.js`
- Portfolio logic: `frontend/src/stores/portfolio.js`, `frontend/src/pages/Portfolio.vue`
