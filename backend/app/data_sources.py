from typing import Optional, Tuple
import time

import pandas as pd
import requests

from .cache import get_cache, set_cache
from .config import CACHE_TTL_SECONDS, ALPHA_VANTAGE_MIN_REQUEST_INTERVAL

_LAST_REQUEST = {"alpha_vantage": 0.0}


def _throttle(provider: str, min_interval: float) -> None:
    now = time.time()
    elapsed = now - _LAST_REQUEST.get(provider, 0.0)
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _LAST_REQUEST[provider] = time.time()


def _to_dataframe_alpha_vantage(series: dict) -> pd.DataFrame:
    df = pd.DataFrame(series).T
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df.rename(columns={
        "1. open": "open",
        "2. high": "high",
        "3. low": "low",
        "4. close": "close",
        "5. volume": "volume",
    })
    df = df.apply(pd.to_numeric, errors="coerce")
    return df


def _extract_time_series(payload: dict) -> Optional[dict]:
    for key, value in payload.items():
        if isinstance(key, str) and key.startswith("Time Series"):
            return value
    return None


def fetch_alpha_vantage_series(
    symbol: str,
    api_key: str,
    interval: str,
    outputsize: str,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    if not api_key:
        return None, "ALPHA_VANTAGE_KEY not set"
    cache_key = f"alpha_vantage:{symbol}:{interval}:{outputsize}"
    cached = get_cache(cache_key, CACHE_TTL_SECONDS)
    if cached is not None:
        return pd.read_json(cached, orient="split"), None

    url = "https://www.alphavantage.co/query"
    _throttle("alpha_vantage", ALPHA_VANTAGE_MIN_REQUEST_INTERVAL)
    if interval in {"1d", "daily"}:
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "apikey": api_key,
            "outputsize": outputsize,
        }
    elif interval in {"1w", "weekly"}:
        params = {
            "function": "TIME_SERIES_WEEKLY",
            "symbol": symbol,
            "apikey": api_key,
        }
    elif interval in {"1m", "monthly"}:
        params = {
            "function": "TIME_SERIES_MONTHLY",
            "symbol": symbol,
            "apikey": api_key,
        }
    else:
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": interval,
            "apikey": api_key,
            "outputsize": outputsize,
        }
    response = requests.get(url, params=params, timeout=20)
    if not response.ok:
        return None, f"HTTP {response.status_code} from Alpha Vantage"
    payload = response.json()
    series = _extract_time_series(payload)
    if not series:
        reason = payload.get("Note") or payload.get("Error Message") or payload.get("Information")
        return None, reason or "Missing time series in response"

    df = _to_dataframe_alpha_vantage(series)
    set_cache(cache_key, df.to_json(orient="split"))
    return df, None


def fetch_fred_series(series_id: str, api_key: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    if not api_key or api_key.startswith("your_"):
        return None, "FRED_API_KEY not set"
    cache_key = f"fred:{series_id}"
    cached = get_cache(cache_key, CACHE_TTL_SECONDS)
    if cached is not None:
        return pd.read_json(cached, orient="split"), None

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": "2000-01-01",
    }
    response = requests.get(url, params=params, timeout=20)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not response.ok:
        msg = payload.get("error_message") or payload.get("message") or f"HTTP {response.status_code} from FRED"
        return None, msg
    if payload.get("error_code") or payload.get("error_message"):
        return None, payload.get("error_message") or "FRED error"
    observations = payload.get("observations")
    if not observations:
        return None, "No observations returned"

    df = pd.DataFrame(observations)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).set_index("date").sort_index()
    df = df.rename(columns={"value": "close"})

    set_cache(cache_key, df.to_json(orient="split"))
    return df, None
