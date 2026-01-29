import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .asset_cache import get_entry, set_entry
from .config import ALPHA_VANTAGE_MIN_REQUEST_INTERVAL, STOOQ_MIN_REQUEST_DELAY_SECONDS
from .providers import fetch_alpha_daily, fetch_stooq_daily
from .usage import (
    can_use_alpha,
    record_provider_call,
    record_request,
    record_stooq_failure,
    usage_snapshot,
    wait_for_alpha_slot,
)


def _now() -> float:
    return time.time()


def _jitter_minutes(key: str, max_minutes: int = 30) -> int:
    return abs(hash(key)) % (max_minutes + 1)


def _next_day_at(hour: int, minute: int, key: str) -> float:
    now = datetime.now()
    target = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    jitter = _jitter_minutes(key)
    return (target + timedelta(minutes=jitter)).timestamp()


def _expiry_for_provider(provider: str, key: str) -> float:
    if provider == "alpha":
        return _next_day_at(6, 0, key)
    return _next_day_at(1, 0, key)


def _to_dataframe(data: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(data)
    df["t"] = pd.to_datetime(df["t"])
    df = df.set_index("t").sort_index()
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    return df


def _is_insufficient(data: List[Dict[str, Any]], interval: str, chart_points: int) -> bool:
    if interval not in {"1d", "daily"}:
        return False
    if chart_points > 90:
        return False
    return len(data[-chart_points:]) < 25


def fetch_stock_history(
    symbol: str,
    stooq_symbol: Optional[str],
    interval: str,
    chart_points: int,
    outputsize: str,
    mode: str,
    alpha_key: str,
) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
    cache_key = f"stock:{symbol}:daily"
    cached = get_entry(cache_key)
    now = _now()
    if cached and cached.get("expires_at", 0) > now and mode != "force":
        record_request(cache_hit=True)
        meta = {
            "provider": cached.get("provider"),
            "source_symbol": cached.get("source_symbol"),
            "fetched_at": cached.get("fetched_at"),
            "expires_at": cached.get("expires_at"),
            "is_stale": False,
            "cache_status": "hit",
        }
        return _to_dataframe(cached.get("data", [])), meta

    stooq_error = None
    if mode == "force" or not cached or cached.get("expires_at", 0) <= now:
        data, err = fetch_stooq_daily(symbol, stooq_symbol)
        time.sleep(STOOQ_MIN_REQUEST_DELAY_SECONDS)
        if data and not _is_insufficient(data, interval, chart_points):
            expires_at = _expiry_for_provider("stooq", symbol)
            entry = {
                "provider": "stooq",
                "source_symbol": (stooq_symbol or "").lower() or None,
                "fetched_at": now,
                "expires_at": expires_at,
                "data": data,
            }
            set_entry(cache_key, entry)
            record_request(cache_hit=False)
            return _to_dataframe(data), {
                "provider": "stooq",
                "source_symbol": entry["source_symbol"],
                "fetched_at": now,
                "expires_at": expires_at,
                "is_stale": False,
                "cache_status": "miss",
            }
        if data and _is_insufficient(data, interval, chart_points):
            stooq_error = "insufficient"
            record_stooq_failure()
        if err:
            stooq_error = err
            record_stooq_failure()

    alpha_allowed = mode == "force" or (not cached or cached.get("expires_at", 0) <= now)
    if alpha_allowed and alpha_key and can_use_alpha(now):
        wait_for_alpha_slot()
        data, err = fetch_alpha_daily(symbol, alpha_key, outputsize=outputsize)
        record_provider_call("alpha", now)
        time.sleep(ALPHA_VANTAGE_MIN_REQUEST_INTERVAL)
        if data:
            expires_at = _expiry_for_provider("alpha", symbol)
            entry = {
                "provider": "alpha",
                "source_symbol": symbol,
                "fetched_at": now,
                "expires_at": expires_at,
                "data": data,
            }
            set_entry(cache_key, entry)
            record_request(cache_hit=False)
            return _to_dataframe(data), {
                "provider": "alpha",
                "source_symbol": symbol,
                "fetched_at": now,
                "expires_at": expires_at,
                "is_stale": False,
                "cache_status": "miss",
                "alpha_error": err,
                "stooq_error": stooq_error,
            }

    if cached:
        record_request(cache_hit=True)
        return _to_dataframe(cached.get("data", [])), {
            "provider": cached.get("provider"),
            "source_symbol": cached.get("source_symbol"),
            "fetched_at": cached.get("fetched_at"),
            "expires_at": cached.get("expires_at"),
            "is_stale": True,
            "cache_status": "stale",
            "stooq_error": stooq_error,
        }

    record_request(cache_hit=False)
    return None, {
        "provider": None,
        "source_symbol": stooq_symbol,
        "fetched_at": None,
        "expires_at": None,
        "is_stale": False,
        "cache_status": "miss",
        "stooq_error": stooq_error,
    }


def usage_summary() -> Dict[str, Any]:
    return usage_snapshot()
