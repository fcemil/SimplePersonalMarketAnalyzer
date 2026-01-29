from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import TRADING_DAYS_IN_MONTH


@dataclass
class AssetAnalysis:
    name: str
    symbol: str
    asset_type: str
    label: str
    score: int
    reasons: List[str]
    features: Dict[str, float]
    ohlc: Optional[List[Dict[str, float]]]
    series: List[float]
    dates: List[str]


def _compute_features(df: pd.DataFrame) -> Dict[str, float]:
    window = df.tail(TRADING_DAYS_IN_MONTH).copy()
    close = window["close"]

    ret_1m = (close.iloc[-1] / close.iloc[0]) - 1
    vol_1m = close.pct_change().std() * np.sqrt(252)
    ma20 = close.rolling(20).mean()
    ma20_valid = ma20.dropna()
    if len(ma20_valid) < 5 or ma20_valid.iloc[-5] == 0:
        slope = 0.0
    else:
        slope = (ma20_valid.iloc[-1] - ma20_valid.iloc[-5]) / ma20_valid.iloc[-5]
    drawdown = (close / close.cummax() - 1).min()

    return {
        "ret_1m": float(ret_1m),
        "vol_1m": float(vol_1m),
        "ma20_slope": float(slope),
        "drawdown_1m": float(drawdown),
    }


def _score_asset(features: Dict[str, float]) -> Tuple[str, int, List[str]]:
    score = 0
    reasons: List[str] = []

    if features["ret_1m"] > 0.03:
        score += 2
        reasons.append("Positive 1-month return (over +3%).")
    elif features["ret_1m"] < -0.03:
        score -= 2
        reasons.append("Negative 1-month return (below -3%).")

    if features["ma20_slope"] > 0.01:
        score += 1
        reasons.append("Rising 20-day moving average.")
    elif features["ma20_slope"] < -0.01:
        score -= 1
        reasons.append("Falling 20-day moving average.")

    if features["drawdown_1m"] < -0.08:
        score -= 1
        reasons.append("Large 1-month drawdown.")

    label = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"
    return label, score, reasons


def analyze_asset(name: str, symbol: str, asset_type: str, df: pd.DataFrame) -> AssetAnalysis:
    df = df.copy()
    df = df.dropna(subset=["close"])
    if len(df) < TRADING_DAYS_IN_MONTH + 5:
        raise ValueError("Not enough data points")

    features = _compute_features(df)
    label, score, reasons = _score_asset(features)

    tail = df.tail(TRADING_DAYS_IN_MONTH)
    series = tail["close"].round(4).tolist()
    dates = [d.strftime("%Y-%m-%d") for d in tail.index]
    ohlc = None
    if {"open", "high", "low", "close"}.issubset(tail.columns):
        ohlc = [
            {
                "time": d.strftime("%Y-%m-%d"),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
            for d, row in tail[["open", "high", "low", "close"]].iterrows()
        ]

    return AssetAnalysis(
        name=name,
        symbol=symbol,
        asset_type=asset_type,
        label=label,
        score=score,
        reasons=reasons,
        features=features,
        ohlc=ohlc,
        series=series,
        dates=dates,
    )
