"""
Dashboard module - Flask REST API for the MarketAnalyzer backend.

Provides endpoints for:
- Fetching analyzed asset data (stocks and commodities) with signals
- Managing watchlist (add/remove stocks)
- Refreshing individual asset data
- Serving the main dashboard page

The API handles both cached and fresh data, coordinates multiple data providers
(Stooq, Alpha Vantage, FRED), and returns analyzed signals with technical indicators.
"""
import json
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

# Load environment variables from .env file (API keys, etc.)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

from .analysis import AssetAnalysis, analyze_asset
from .asset_manager import fetch_stock_history, usage_summary
from .config import ALPHA_VANTAGE_KEY, FRED_API_KEY, POPULAR_COMMODITIES, ANALYSIS_WINDOW_DAYS, DRAWDOWN_WINDOW_DAYS
from .data_sources import fetch_fred_series
from .providers import infer_currency, latest_from_history, resample_history
from .watchlist import add_symbol, load_watchlist, remove_symbol

# Initialize Flask application
app = Flask(__name__)


def _safe_analyze_assets(
    interval: str,
    chart_points: int,
    outputsize: str,
    stooq_map: dict,
    mode: str,
) -> List[tuple]:
    """
    Fetch and analyze all watchlist stocks and configured commodities.
    
    Args:
        interval: Time interval for data ('1d', '1w', '1m')
        chart_points: Number of data points to return for charting
        outputsize: API output size ('compact' or 'full')
        stooq_map: Optional mapping of symbols to Stooq-specific symbols
        mode: Fetch mode ('daily' for cache, 'force' to refresh)
    
    Returns:
        Tuple of (results, errors) where results is a list of (AssetAnalysis, metadata) tuples
        and errors is a list of error messages encountered during fetch/analysis.
    """
    results: List[tuple] = []
    errors: List[str] = []

    # Validate API keys are configured
    if not ALPHA_VANTAGE_KEY:
        errors.append("Stocks: ALPHA_VANTAGE_KEY not loaded (check .env location and restart server)")
    if not FRED_API_KEY:
        errors.append("Commodities: FRED_API_KEY not loaded (check .env location and restart server)")

    # Process each stock symbol in the watchlist
    for symbol in load_watchlist():
        try:
            # Fetch historical price data from cache or data providers
            df, meta = fetch_stock_history(
                symbol=symbol,
                stooq_symbol=stooq_map.get(symbol),
                interval=interval,
                chart_points=chart_points,
                outputsize=outputsize,
                mode=mode,
                alpha_key=ALPHA_VANTAGE_KEY,
            )
            # Handle case where no data is available for this symbol
            if df is None:
                errors.append(f"Stocks: {symbol} - missing history")
                meta["missing"] = True
                # Create a neutral analysis result with zero features for missing data
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
            # Resample data to the requested interval (daily → weekly/monthly if needed)
            df = resample_history(df, interval)
            meta["sample_count"] = int(len(df))
        except Exception:
            errors.append(f"Stocks: {symbol} - missing history (cache fetch failed)")
            continue
        try:
            # Analyze the asset to compute signals and technical features
            results.append((analyze_asset(symbol, symbol, "stock", df, chart_points), meta))
        except Exception:
            errors.append(f"Stocks: insufficient data for {symbol}")

    # Process configured commodity symbols from FRED
    for name, meta in POPULAR_COMMODITIES.items():
        if meta.get("source") == "fred":
            # Fetch commodity data from FRED API
            df, err = fetch_fred_series(meta["series_id"], FRED_API_KEY)
            if df is None:
                errors.append(f"Commodities: {name} - {err or 'missing data (check API key / series)'}")
                continue
            try:
                # Analyze commodity data and add to results
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
    """
    Render the main dashboard HTML page.
    
    Fetches and analyzes watchlist assets with default parameters,
    then renders the index.html template with the asset data.
    """
    # Fetch all assets with default daily interval and 120 chart points
    assets, errors = _safe_analyze_assets("1d", 120, "compact", {}, "daily")
    asset_rows = [a for a, _ in assets]

    # Build simplified payload for frontend consumption
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

    # Render the dashboard template with asset data and errors
    return render_template(
        "index.html",
        assets=asset_rows,
        assets_json=payload_json,
        errors=errors,
    )


@app.get("/api/assets")
def api_assets():
    """
    GET /api/assets - Fetch all watchlist stocks and commodities with analysis.
    
    Query parameters:
        interval: Time interval ('1d', '1w', '1m')
        chart_points: Number of data points for charts (default 60)
        outputsize: API output size ('compact' or 'full')
        mode: Fetch mode ('daily' uses cache, 'force' refreshes)
        stooq_map: JSON mapping of symbols to Stooq codes
    
    Returns:
        JSON with { assets: [...], errors: [...], usage: {...} }
    """
    # Parse query parameters with defaults
    interval = request.args.get("interval", "1d")
    outputsize = request.args.get("outputsize", "compact")
    chart_points = int(request.args.get("chart_points", "60"))
    mode = request.args.get("mode", "daily")
    stooq_map_raw = request.args.get("stooq_map", "")
    
    # Parse stooq_map JSON if provided
    stooq_map = {}
    if stooq_map_raw:
        try:
            stooq_map = json.loads(stooq_map_raw)
        except json.JSONDecodeError:
            stooq_map = {}
    
    # Limit chart points to reasonable maximums per interval to avoid excessive data transfer
    if interval in {"1d", "daily"} and chart_points > 1260:
        chart_points = 1260
    if interval in {"1w", "weekly"} and chart_points > 520:
        chart_points = 520
    if interval in {"1m", "monthly"} and chart_points > 240:
        chart_points = 240
    
    # Fetch and analyze all assets
    assets, errors = _safe_analyze_assets(interval, chart_points, outputsize, stooq_map, mode)
    # Build detailed response payload for each asset
    payload = []
    for a, meta in assets:
        payload.append(
            {
                "name": a.name,
                "symbol": a.symbol,
                "type": a.asset_type,
                "label": a.label,  # Signal: 'bullish', 'bearish', or 'neutral'
                "score": a.score,  # Numeric score based on technical indicators
                "reasons": a.reasons,  # Human-readable reasons for the signal
                "features": a.features,  # Technical features (returns, volatility, etc.)
                "latest_price": a.latest_price,
                "change_pct": a.change_pct,  # Daily price change percentage
                "ohlc": a.ohlc,  # Candlestick data for charting
                "series": a.series,  # Close price series for simple line charts
                "dates": a.dates,  # Date labels for chart x-axis
                "currency": infer_currency(a.symbol, a.asset_type),
                "analysis_window_days": ANALYSIS_WINDOW_DAYS,
                "drawdown_window_days": DRAWDOWN_WINDOW_DAYS,
                "feature_contributions": a.feature_contributions,  # Breakdown of score components
                "sample_count": meta.get("sample_count"),
                **meta,  # Include provider metadata (cache status, fetch times, etc.)
            }
        )
    # Return assets with errors and API usage statistics
    return jsonify({"assets": payload, "errors": errors, "usage": usage_summary()})


@app.get("/api/asset")
def api_asset():
    """
    GET /api/asset - Fetch and analyze a single asset.
    
    Query parameters:
        symbol: Stock symbol or commodity series ID (required)
        type: Asset type ('stock' or 'commodity') (required)
        interval: Time interval ('1d', '1w', '1m')
        chart_points: Number of data points for charts
        outputsize: API output size ('compact' or 'full')
        refresh: Force refresh from API ('1' = yes, '0' = no)
        mode: Fetch mode ('daily' or 'force')
        stooq_symbol: Optional Stooq-specific symbol override
    
    Returns:
        JSON with { asset: {...} } containing analysis and chart data
    """
    # Parse and validate required parameters
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
    # Limit chart points per interval
    if interval in {"1d", "daily"} and chart_points > 1260:
        chart_points = 1260
    if interval in {"1w", "weekly"} and chart_points > 520:
        chart_points = 520
    if interval in {"1m", "monthly"} and chart_points > 240:
        chart_points = 240

    # Fetch data based on asset type
    if asset_type == "stock":
        try:
            # Fetch stock history from cache or providers
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
            # Resample to requested interval
            df = resample_history(df, interval)
        except Exception:
            return jsonify({"error": "missing history"}), 400
        # Analyze the stock data
        asset = analyze_asset(symbol, symbol, "stock", df, chart_points)
        # Extract latest price and daily change
        latest, change = latest_from_history(df)
        asset.latest_price = latest
        asset.change_pct = change
    else:
        # Fetch commodity data from FRED
        df, err = fetch_fred_series(symbol, FRED_API_KEY)
        if df is None:
            return jsonify({"error": err or "missing data"}), 400
        # Analyze commodity data
        asset = analyze_asset(symbol, symbol, "commodity", df, chart_points)
        if refresh:
            # Update latest price for refreshed commodity data
            latest, change = latest_from_history(df)
            asset.latest_price = latest
            asset.change_pct = change

    # Build complete asset payload
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
    # Add provider-specific metadata
    if asset_type == "stock":
        payload.update(meta)  # Include cache status, provider info, etc.
    else:
        payload["provider"] = "fred"
    return jsonify({"asset": payload})


@app.get("/api/watchlist")
def get_watchlist():
    """
    GET /api/watchlist - Retrieve the current watchlist.
    
    Returns:
        JSON with { stocks: [...] } containing all symbols in the watchlist
    """
    return jsonify({"stocks": load_watchlist()})


@app.post("/api/watchlist")
def post_watchlist():
    """
    POST /api/watchlist - Add a symbol to the watchlist.
    
    Request body:
        { "symbol": "AAPL" }
    
    Returns:
        JSON with { stocks: [...] } containing updated watchlist
    """
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "")
    return jsonify({"stocks": add_symbol(symbol)})


@app.delete("/api/watchlist/<symbol>")
def delete_watchlist(symbol: str):
    """
    DELETE /api/watchlist/<symbol> - Remove a symbol from the watchlist.
    
    Args:
        symbol: Stock symbol to remove from watchlist
    
    Returns:
        JSON with { stocks: [...] } containing updated watchlist
    """
    return jsonify({"stocks": remove_symbol(symbol)})
