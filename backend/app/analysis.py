"""
Analysis module - Technical analysis and signal generation.

Computes trading signals based on simple technical indicators:
- 30-day returns
- 30-day volatility (annualized)
- 20-day moving average slope
- 3-month maximum drawdown

Scoring system:
- Bullish (score >= 2): Strong positive signals
- Bearish (score <= -2): Strong negative signals  
- Neutral (otherwise): Mixed or weak signals
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import ANALYSIS_WINDOW_DAYS, DRAWDOWN_WINDOW_DAYS


@dataclass
class AssetAnalysis:
    """
    Container for asset analysis results.
    
    Includes both the computed signals/features and the raw price data
    formatted for frontend charting.
    """
    name: str
    symbol: str
    asset_type: str
    label: str  # 'bullish', 'bearish', or 'neutral'
    score: int  # Numeric score (-3 to +3 typically)
    reasons: List[str]  # Human-readable signal explanations
    features: Dict[str, float]  # Raw feature values
    latest_price: Optional[float]
    change_pct: Optional[float]
    ohlc: Optional[List[Dict[str, float]]]  # Candlestick data
    series: List[float]  # Close prices only
    dates: List[str]  # Date labels
    feature_contributions: List[Dict[str, float]]  # Score breakdown


def _compute_features(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate technical features from price history.
    
    Features computed:
    - ret_30d: 30-day total return
    - vol_30d: Annualized volatility (using 252 trading days)
    - ma20_slope: 5-day rate of change in 20-day moving average
    - drawdown_3m: Maximum drawdown over 3 months
    
    Args:
        df: DataFrame with 'close' column and datetime index
    
    Returns:
        Dict of feature name to float value
    """
    # Use the most recent ANALYSIS_WINDOW_DAYS (typically 30 days)
    window = df.tail(ANALYSIS_WINDOW_DAYS).copy()
    close = window["close"]

    # 30-day return: (latest / first) - 1
    ret_30d = (close.iloc[-1] / close.iloc[0]) - 1
    
    # Annualized volatility: std dev of daily returns * sqrt(252)
    vol_30d = close.pct_change().std() * np.sqrt(252)
    
    # MA20 slope: % change in MA over last 5 days
    ma20 = close.rolling(20).mean()
    ma20_valid = ma20.dropna()
    if len(ma20_valid) < 5 or ma20_valid.iloc[-5] == 0:
        slope = 0.0
    else:
        slope = (ma20_valid.iloc[-1] - ma20_valid.iloc[-5]) / ma20_valid.iloc[-5]
    
    # Maximum drawdown over DRAWDOWN_WINDOW_DAYS (typically 63 days = 3 months)
    drawdown_window = df.tail(DRAWDOWN_WINDOW_DAYS)["close"]
    drawdown = (drawdown_window / drawdown_window.cummax() - 1).min()

    return {
        "ret_30d": float(ret_30d),
        "vol_30d": float(vol_30d),
        "ma20_slope": float(slope),
        "drawdown_3m": float(drawdown),
    }


def _score_asset(features: Dict[str, float]) -> Tuple[str, int, List[str], List[Dict[str, float]]]:
    """
    Generate trading signal based on technical features.
    
    Scoring rules:
    - +2 if 30-day return > +3%
    - -2 if 30-day return < -3%
    - +1 if MA20 slope > +1%
    - -1 if MA20 slope < -1%
    - -1 if max drawdown < -8%
    
    Final label:
    - 'bullish' if score >= 2
    - 'bearish' if score <= -2
    - 'neutral' otherwise
    
    Returns:
        Tuple of (label, score, reasons, contributions)
        where contributions shows which features contributed to the score
    """
    score = 0
    reasons: List[str] = []
    contributions: List[Dict[str, float]] = []

    # Evaluate 30-day return
    if features["ret_30d"] > 0.03:
        score += 2
        reasons.append("Positive 30-day return (over +3%).")
        contributions.append({"feature": "Return(30D)", "value": features["ret_30d"], "impact": 2})
    elif features["ret_30d"] < -0.03:
        score -= 2
        reasons.append("Negative 30-day return (below -3%).")
        contributions.append({"feature": "Return(30D)", "value": features["ret_30d"], "impact": -2})

    # Evaluate MA20 slope (trend)
    if features["ma20_slope"] > 0.01:
        score += 1
        reasons.append("Rising 20-day moving average.")
        contributions.append({"feature": "MA20 Slope", "value": features["ma20_slope"], "impact": 1})
    elif features["ma20_slope"] < -0.01:
        score -= 1
        reasons.append("Falling 20-day moving average.")
        contributions.append({"feature": "MA20 Slope", "value": features["ma20_slope"], "impact": -1})

    # Evaluate drawdown (risk measure)
    if features["drawdown_3m"] < -0.08:
        score -= 1
        reasons.append("Large 3-month drawdown.")
        contributions.append({"feature": "Drawdown(3M)", "value": features["drawdown_3m"], "impact": -1})

    # Determine label based on final score
    label = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"
    return label, score, reasons, contributions


def analyze_asset(
    name: str,
    symbol: str,
    asset_type: str,
    df: pd.DataFrame,
    chart_points: int,
) -> AssetAnalysis:
    """
    Analyze an asset's price history and generate trading signals.
    
    Steps:
    1. Compute technical features
    2. Score features to generate signal
    3. Extract chart data (OHLC and close series)
    4. Package everything into AssetAnalysis object
    
    Args:
        name: Display name (e.g., 'AAPL' or 'WTI Crude')
        symbol: Trading symbol or series ID
        asset_type: 'stock' or 'commodity'
        df: Price history DataFrame with OHLCV columns
        chart_points: Number of recent data points to include in chart
    
    Returns:
        AssetAnalysis object with signals and chart data
    """
    df = df.copy()
    df = df.dropna(subset=["close"])  # Remove any rows with missing close prices
    
    # Calculate features and generate signal
    features = _compute_features(df)
    label, score, reasons, contributions = _score_asset(features)

    # Extract the most recent data for charting
    chart_tail = df.tail(chart_points)
    series = chart_tail["close"].round(4).tolist()
    dates = [d.strftime("%Y-%m-%d") for d in chart_tail.index]
    
    # Calculate latest price and daily change
    latest_price = None
    change_pct = None
    if len(df) >= 2:
        latest_price = float(df["close"].iloc[-1])
        prev = float(df["close"].iloc[-2])
        if prev != 0:
            change_pct = (latest_price / prev) - 1
    
    # Build OHLC candlestick data if available
    ohlc = None
    if {"open", "high", "low", "close"}.issubset(chart_tail.columns):
        cols = ["open", "high", "low", "close"]
        if "volume" in chart_tail.columns:
            cols.append("volume")
        ohlc = [
            {
                "time": d.strftime("%Y-%m-%d"),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]) if "volume" in row else 0,
            }
            for d, row in chart_tail[cols].iterrows()
        ]

    return AssetAnalysis(
        name=name,
        symbol=symbol,
        asset_type=asset_type,
        label=label,
        score=score,
        reasons=reasons,
        features=features,
        latest_price=latest_price,
        change_pct=change_pct,
        ohlc=ohlc,
        series=series,
        dates=dates,
        feature_contributions=contributions,
    )
