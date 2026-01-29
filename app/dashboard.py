import json
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

from .analysis import AssetAnalysis, analyze_asset
from .config import ALPHA_VANTAGE_KEY, FRED_API_KEY, POPULAR_COMMODITIES
from .data_sources import fetch_alpha_vantage_daily, fetch_fred_series
from .watchlist import add_symbol, load_watchlist, remove_symbol

app = Flask(__name__)


def _safe_analyze_assets() -> List[AssetAnalysis]:
    results: List[AssetAnalysis] = []
    errors: List[str] = []

    if not ALPHA_VANTAGE_KEY:
        errors.append("Stocks: ALPHA_VANTAGE_KEY not loaded (check .env location and restart server)")
    if not FRED_API_KEY:
        errors.append("Commodities: FRED_API_KEY not loaded (check .env location and restart server)")

    for symbol in load_watchlist():
        df, err = fetch_alpha_vantage_daily(symbol, ALPHA_VANTAGE_KEY)
        if df is None:
            errors.append(f"Stocks: {symbol} - {err or 'missing data (check API key / rate limits)'}")
            continue
        try:
            results.append(analyze_asset(symbol, symbol, "stock", df))
        except Exception:
            errors.append(f"Stocks: insufficient data for {symbol}")

    for name, meta in POPULAR_COMMODITIES.items():
        if meta.get("source") == "fred":
            df, err = fetch_fred_series(meta["series_id"], FRED_API_KEY)
            if df is None:
                errors.append(f"Commodities: {name} - {err or 'missing data (check API key / series)'}")
                continue
            try:
                results.append(analyze_asset(name, meta["series_id"], "commodity", df))
            except Exception:
                errors.append(f"Commodities: insufficient data for {name}")

    return results, errors


@app.route("/")
def index():
    assets, errors = _safe_analyze_assets()

    payload = [
        {
            "name": a.name,
            "symbol": a.symbol,
            "type": a.asset_type,
            "label": a.label,
            "score": a.score,
            "reasons": a.reasons,
            "features": a.features,
            "ohlc": a.ohlc,
            "series": a.series,
            "dates": a.dates,
        }
        for a in assets
    ]

    payload_json = json.dumps(payload)

    return render_template(
        "index.html",
        assets=assets,
        assets_json=payload_json,
        errors=errors,
    )


@app.get("/api/watchlist")
def get_watchlist():
    return jsonify({"stocks": load_watchlist()})


@app.post("/api/watchlist")
def post_watchlist():
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "")
    return jsonify({"stocks": add_symbol(symbol)})


@app.delete("/api/watchlist/<symbol>")
def delete_watchlist(symbol: str):
    return jsonify({"stocks": remove_symbol(symbol)})
