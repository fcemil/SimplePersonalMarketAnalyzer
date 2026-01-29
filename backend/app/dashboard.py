import json
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

from .analysis import AssetAnalysis, analyze_asset
from .asset_manager import fetch_stock_history, usage_summary
from .config import ALPHA_VANTAGE_KEY, FRED_API_KEY, POPULAR_COMMODITIES, ANALYSIS_WINDOW_DAYS, DRAWDOWN_WINDOW_DAYS
from .data_sources import fetch_fred_series
from .providers import infer_currency, latest_from_history, resample_history
from .watchlist import add_symbol, load_watchlist, remove_symbol

app = Flask(__name__)


def _safe_analyze_assets(
    interval: str,
    chart_points: int,
    outputsize: str,
    stooq_map: dict,
    mode: str,
) -> List[tuple]:
    results: List[tuple] = []
    errors: List[str] = []

    if not ALPHA_VANTAGE_KEY:
        errors.append("Stocks: ALPHA_VANTAGE_KEY not loaded (check .env location and restart server)")
    if not FRED_API_KEY:
        errors.append("Commodities: FRED_API_KEY not loaded (check .env location and restart server)")

    for symbol in load_watchlist():
        try:
            df, meta = fetch_stock_history(
                symbol=symbol,
                stooq_symbol=stooq_map.get(symbol),
                interval=interval,
                chart_points=chart_points,
                outputsize=outputsize,
                mode=mode,
                alpha_key=ALPHA_VANTAGE_KEY,
            )
            if df is None:
                errors.append(f"Stocks: {symbol} - missing history")
                meta["missing"] = True
                results.append(
                    (
                        AssetAnalysis(
                            name=symbol,
                            symbol=symbol,
                            asset_type="stock",
                            label="neutral",
                            score=0,
                            reasons=["Missing data"],
                            features={"ret_30d": 0.0, "vol_30d": 0.0, "ma20_slope": 0.0, "drawdown_3m": 0.0},
                            latest_price=None,
                            change_pct=None,
                            ohlc=[],
                            series=[],
                            dates=[],
                            feature_contributions=[],
                        ),
                        meta,
                    )
                )
                continue
            df = resample_history(df, interval)
            meta["sample_count"] = int(len(df))
        except Exception:
            errors.append(f"Stocks: {symbol} - missing history (cache fetch failed)")
            continue
        try:
            results.append((analyze_asset(symbol, symbol, "stock", df, chart_points), meta))
        except Exception:
            errors.append(f"Stocks: insufficient data for {symbol}")

    for name, meta in POPULAR_COMMODITIES.items():
        if meta.get("source") == "fred":
            df, err = fetch_fred_series(meta["series_id"], FRED_API_KEY)
            if df is None:
                errors.append(f"Commodities: {name} - {err or 'missing data (check API key / series)'}")
                continue
            try:
                results.append(
                    (
                        analyze_asset(name, meta["series_id"], "commodity", df, chart_points),
                        {"provider": "fred", "sample_count": int(len(df))},
                    )
                )
            except Exception:
                errors.append(f"Commodities: insufficient data for {name}")

    return results, errors


@app.route("/")
def index():
    assets, errors = _safe_analyze_assets("1d", 120, "compact", {}, "daily")
    asset_rows = [a for a, _ in assets]

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
        for a in asset_rows
    ]

    payload_json = json.dumps(payload)

    return render_template(
        "index.html",
        assets=asset_rows,
        assets_json=payload_json,
        errors=errors,
    )


@app.get("/api/assets")
def api_assets():
    interval = request.args.get("interval", "1d")
    outputsize = request.args.get("outputsize", "compact")
    chart_points = int(request.args.get("chart_points", "60"))
    mode = request.args.get("mode", "daily")
    stooq_map_raw = request.args.get("stooq_map", "")
    stooq_map = {}
    if stooq_map_raw:
        try:
            stooq_map = json.loads(stooq_map_raw)
        except json.JSONDecodeError:
            stooq_map = {}
    if interval in {"1d", "daily"} and chart_points > 1260:
        chart_points = 1260
    if interval in {"1w", "weekly"} and chart_points > 520:
        chart_points = 520
    if interval in {"1m", "monthly"} and chart_points > 240:
        chart_points = 240
    assets, errors = _safe_analyze_assets(interval, chart_points, outputsize, stooq_map, mode)
    payload = []
    for a, meta in assets:
        payload.append(
            {
                "name": a.name,
                "symbol": a.symbol,
                "type": a.asset_type,
                "label": a.label,
                "score": a.score,
                "reasons": a.reasons,
                "features": a.features,
                "latest_price": a.latest_price,
                "change_pct": a.change_pct,
                "ohlc": a.ohlc,
                "series": a.series,
                "dates": a.dates,
                "currency": infer_currency(a.symbol, a.asset_type),
                "analysis_window_days": ANALYSIS_WINDOW_DAYS,
                "drawdown_window_days": DRAWDOWN_WINDOW_DAYS,
                "feature_contributions": a.feature_contributions,
                "sample_count": meta.get("sample_count"),
                **meta,
            }
        )
    return jsonify({"assets": payload, "errors": errors, "usage": usage_summary()})


@app.get("/api/asset")
def api_asset():
    symbol = request.args.get("symbol", "").strip()
    asset_type = request.args.get("type", "").strip()
    interval = request.args.get("interval", "1d")
    outputsize = request.args.get("outputsize", "compact")
    chart_points = int(request.args.get("chart_points", "60"))
    refresh = request.args.get("refresh", "0") == "1"
    mode = request.args.get("mode", "daily")
    stooq_symbol = request.args.get("stooq_symbol", "").strip() or None
    if not symbol or not asset_type:
        return jsonify({"error": "symbol and type are required"}), 400
    if interval in {"1d", "daily"} and chart_points > 1260:
        chart_points = 1260
    if interval in {"1w", "weekly"} and chart_points > 520:
        chart_points = 520
    if interval in {"1m", "monthly"} and chart_points > 240:
        chart_points = 240

    if asset_type == "stock":
        try:
            df, meta = fetch_stock_history(
                symbol=symbol,
                stooq_symbol=stooq_symbol,
                interval=interval,
                chart_points=chart_points,
                outputsize=outputsize,
                mode="force" if refresh or mode == "force" else "daily",
                alpha_key=ALPHA_VANTAGE_KEY,
            )
            if df is None:
                return jsonify({"error": "missing history"}), 400
            df = resample_history(df, interval)
        except Exception:
            return jsonify({"error": "missing history"}), 400
        asset = analyze_asset(symbol, symbol, "stock", df, chart_points)
        latest, change = latest_from_history(df)
        asset.latest_price = latest
        asset.change_pct = change
    else:
        df, err = fetch_fred_series(symbol, FRED_API_KEY)
        if df is None:
            return jsonify({"error": err or "missing data"}), 400
        asset = analyze_asset(symbol, symbol, "commodity", df, chart_points)
        if refresh:
            latest, change = latest_from_history(df)
            asset.latest_price = latest
            asset.change_pct = change

    payload = {
        "name": asset.name,
        "symbol": asset.symbol,
        "type": asset.asset_type,
        "label": asset.label,
        "score": asset.score,
        "reasons": asset.reasons,
        "features": asset.features,
        "latest_price": asset.latest_price,
        "change_pct": asset.change_pct,
        "ohlc": asset.ohlc,
        "series": asset.series,
        "dates": asset.dates,
        "currency": infer_currency(asset.symbol, asset.asset_type),
        "analysis_window_days": ANALYSIS_WINDOW_DAYS,
        "drawdown_window_days": DRAWDOWN_WINDOW_DAYS,
        "feature_contributions": asset.feature_contributions,
        "sample_count": int(len(df)),
    }
    if asset_type == "stock":
        payload.update(meta)
    else:
        payload["provider"] = "fred"
    return jsonify({"asset": payload})


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
