from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import ANALYSIS_WINDOW_DAYS, DRAWDOWN_WINDOW_DAYS


@dataclass
class AssetAnalysis:
    name: str
    symbol: str
    asset_type: str
    label: str
    score: int
    reasons: List[str]
    features: Dict[str, float]
    latest_price: Optional[float]
    change_pct: Optional[float]
    ohlc: Optional[List[Dict[str, float]]]
    series: List[float]
    dates: List[str]
    feature_contributions: List[Dict[str, float]]


def _compute_features(df: pd.DataFrame) -> Dict[str, float]:
    window = df.tail(ANALYSIS_WINDOW_DAYS).copy()
    close = window["close"]

    ret_30d = (close.iloc[-1] / close.iloc[0]) - 1
    vol_30d = close.pct_change().std() * np.sqrt(252)
    ma20 = close.rolling(20).mean()
    ma20_valid = ma20.dropna()
    if len(ma20_valid) < 5 or ma20_valid.iloc[-5] == 0:
        slope = 0.0
    else:
        slope = (ma20_valid.iloc[-1] - ma20_valid.iloc[-5]) / ma20_valid.iloc[-5]
    drawdown_window = df.tail(DRAWDOWN_WINDOW_DAYS)["close"]
    drawdown = (drawdown_window / drawdown_window.cummax() - 1).min()

    return {
        "ret_30d": float(ret_30d),
        "vol_30d": float(vol_30d),
        "ma20_slope": float(slope),
        "drawdown_3m": float(drawdown),
    }


def _score_asset(features: Dict[str, float]) -> Tuple[str, int, List[str], List[Dict[str, float]]]:
    score = 0
    reasons: List[str] = []
    contributions: List[Dict[str, float]] = []

    if features["ret_30d"] > 0.03:
        score += 2
        reasons.append("Positive 30-day return (over +3%).")
        contributions.append({"feature": "Return(30D)", "value": features["ret_30d"], "impact": 2})
    elif features["ret_30d"] < -0.03:
        score -= 2
        reasons.append("Negative 30-day return (below -3%).")
        contributions.append({"feature": "Return(30D)", "value": features["ret_30d"], "impact": -2})

    if features["ma20_slope"] > 0.01:
        score += 1
        reasons.append("Rising 20-day moving average.")
        contributions.append({"feature": "MA20 Slope", "value": features["ma20_slope"], "impact": 1})
    elif features["ma20_slope"] < -0.01:
        score -= 1
        reasons.append("Falling 20-day moving average.")
        contributions.append({"feature": "MA20 Slope", "value": features["ma20_slope"], "impact": -1})

    if features["drawdown_3m"] < -0.08:
        score -= 1
        reasons.append("Large 3-month drawdown.")
        contributions.append({"feature": "Drawdown(3M)", "value": features["drawdown_3m"], "impact": -1})

    label = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"
    return label, score, reasons, contributions


def analyze_asset(
    name: str,
    symbol: str,
    asset_type: str,
    df: pd.DataFrame,
    chart_points: int,
) -> AssetAnalysis:
    df = df.copy()
    df = df.dropna(subset=["close"])
    features = _compute_features(df)
    label, score, reasons, contributions = _score_asset(features)

    chart_tail = df.tail(chart_points)
    series = chart_tail["close"].round(4).tolist()
    dates = [d.strftime("%Y-%m-%d") for d in chart_tail.index]
    latest_price = None
    change_pct = None
    if len(df) >= 2:
        latest_price = float(df["close"].iloc[-1])
        prev = float(df["close"].iloc[-2])
        if prev != 0:
            change_pct = (latest_price / prev) - 1
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
