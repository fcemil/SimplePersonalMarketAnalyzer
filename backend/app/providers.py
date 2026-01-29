import csv
import io
import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd
import requests

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")


def _ensure_cache_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)


def _stooq_symbol(symbol: str) -> str:
    base = symbol.lower()
    if base.endswith(
        (
            ".us",
            ".uk",
            ".de",
            ".to",
            ".trt",
            ".trv",
            ".lon",
            ".as",
            ".pa",
            ".sw",
            ".mi",
            ".hk",
            ".ss",
            ".sz",
        )
    ):
        return base
    return base.replace(".", "-") + ".us"


def infer_currency(symbol: str, asset_type: str) -> str:
    if asset_type == "commodity":
        return "USD"
    base = symbol.lower()
    if base.endswith(".us"):
        return "USD"
    if base.endswith((".uk", ".lon")):
        return "GBP"
    if base.endswith((".de", ".dex", ".xetra", ".fr", ".pa", ".mi", ".as")):
        return "EUR"
    if base.endswith((".to", ".trt", ".trv")):
        return "CAD"
    if base.endswith(".sw"):
        return "CHF"
    if base.endswith(".hk"):
        return "HKD"
    if base.endswith((".ss", ".sh", ".sz")):
        return "CNY"
    return "USD"


def _cache_path(symbol: str) -> str:
    safe = symbol.upper().replace("/", "_").replace(".", "-")
    return os.path.join(CACHE_DIR, f"stooq_{safe}.csv")


def _read_cache(symbol: str) -> Optional[pd.DataFrame]:
    path = _cache_path(symbol)
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if "Date" not in df.columns:
        return None
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    return df


def _write_cache(symbol: str, df: pd.DataFrame) -> None:
    _ensure_cache_dir()
    path = _cache_path(symbol)
    df = df.reset_index()
    df.to_csv(path, index=False)


def fetch_stooq_daily(symbol: str, stooq_symbol: Optional[str] = None) -> Tuple[Optional[List[dict]], Optional[str]]:
    stooq_code = (stooq_symbol or _stooq_symbol(symbol)).lower()
    params = {"s": stooq_code, "i": "d"}
    url = "https://stooq.com/q/d/l/"
    response = requests.get(url, params=params, timeout=20)
    if not response.ok:
        return None, "network"
    text = response.text.strip()
    if not text or text.lower().startswith("no data"):
        return None, "symbol_not_found"
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        if not row or not row.get("Date"):
            continue
        rows.append(row)
    if not rows:
        return None, "symbol_not_found"
    parsed = []
    for row in rows:
        try:
            parsed.append(
                {
                    "t": row["Date"],
                    "o": float(row.get("Open") or 0),
                    "h": float(row.get("High") or 0),
                    "l": float(row.get("Low") or 0),
                    "c": float(row.get("Close") or 0),
                    "v": float(row.get("Volume") or 0),
                }
            )
        except (TypeError, ValueError):
            continue
    if not parsed:
        return None, "malformed"
    parsed.sort(key=lambda x: x["t"])
    return parsed, None


def fetch_alpha_daily(symbol: str, api_key: str, outputsize: str = "compact") -> Tuple[Optional[List[dict]], Optional[str]]:
    if not api_key:
        return None, "ALPHA_VANTAGE_KEY not set"
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "apikey": api_key,
        "outputsize": outputsize,
    }
    response = requests.get(url, params=params, timeout=20)
    if not response.ok:
        return None, f"HTTP {response.status_code}"
    payload = response.json()
    series = None
    for key, value in payload.items():
        if isinstance(key, str) and key.startswith("Time Series"):
            series = value
            break
    if not series:
        reason = payload.get("Note") or payload.get("Error Message") or payload.get("Information")
        return None, reason or "Missing time series"
    parsed = []
    for date_str, values in series.items():
        try:
            parsed.append(
                {
                    "t": date_str,
                    "o": float(values.get("1. open") or 0),
                    "h": float(values.get("2. high") or 0),
                    "l": float(values.get("3. low") or 0),
                    "c": float(values.get("4. close") or 0),
                    "v": float(values.get("6. volume") or values.get("5. volume") or 0),
                }
            )
        except (TypeError, ValueError):
            continue
    if not parsed:
        return None, "Malformed Alpha Vantage response"
    parsed.sort(key=lambda x: x["t"])
    return parsed, None


def _fetch_stooq(symbol: str, start: Optional[datetime], end: Optional[datetime]) -> pd.DataFrame:
    params = {"s": _stooq_symbol(symbol), "i": "d"}
    if start and end:
        params["d1"] = start.strftime("%Y%m%d")
        params["d2"] = end.strftime("%Y%m%d")
    url = "https://stooq.com/q/d/l/"
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.text))
    if "Date" not in df.columns:
        raise ValueError("Unexpected Stooq response")
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    return df


def get_history(symbol: str, refresh: bool) -> pd.DataFrame:
    cached = _read_cache(symbol)
    if cached is None or cached.empty:
        df = _fetch_stooq(symbol, None, None)
        _write_cache(symbol, df)
        return df

    if not refresh:
        return cached

    last_date = cached.index.max()
    start = last_date + timedelta(days=1)
    end = datetime.utcnow()
    if start.date() > end.date():
        return cached

    try:
        new_data = _fetch_stooq(symbol, start, end)
    except Exception:
        return cached
    if new_data.empty:
        return cached

    combined = pd.concat([cached, new_data]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    _write_cache(symbol, combined)
    return combined


def latest_from_history(df: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
    if df is None or df.empty:
        return None, None
    latest = float(df["close"].iloc[-1])
    prev = float(df["close"].iloc[-2]) if len(df) > 1 else None
    change = None
    if prev and prev != 0:
        change = (latest / prev) - 1
    return latest, change


def resample_history(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    if interval in {"1d", "daily"}:
        return df
    if interval in {"1w", "weekly"}:
        rule = "W-FRI"
    elif interval in {"1m", "monthly"}:
        rule = "M"
    else:
        return df

    if {"open", "high", "low"}.issubset(df.columns) is False:
        df = df.copy()
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"] = df["close"]
    if "volume" not in df.columns:
        df = df.copy()
        df["volume"] = 0

    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    resampled = df.resample(rule).agg(agg).dropna(subset=["close"])
    return resampled


def fetch_alpha_quote(symbol: str, api_key: str) -> Tuple[Optional[float], Optional[float]]:
    if not api_key:
        return None, None
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": api_key,
    }
    response = requests.get(url, params=params, timeout=20)
    if not response.ok:
        return None, None
    payload = response.json()
    quote = payload.get("Global Quote") or {}
    price = quote.get("05. price")
    prev = quote.get("08. previous close")
    try:
        latest = float(price)
    except (TypeError, ValueError):
        latest = None
    try:
        prev_close = float(prev)
    except (TypeError, ValueError):
        prev_close = None
    change = None
    if latest is not None and prev_close:
        change = (latest / prev_close) - 1
    return latest, change
