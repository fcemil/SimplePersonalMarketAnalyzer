"""
Asset Manager module - Coordinates data fetching from multiple providers with caching.

This module implements a smart caching layer that:
- Tries Stooq (free, unlimited) as primary provider for daily data
- Falls back to Alpha Vantage (quota-limited) when Stooq fails
- Returns stale cache if both providers fail
- Respects API rate limits and quota budgets
- Manages cache expiry with jittered refresh times

Cache Strategy:
- Stooq cache expires at ~1am UTC + jitter (refresh overnight)
- Alpha cache expires at ~6am UTC + jitter (refresh in early morning)
- Jitter prevents all symbols from refreshing at exactly the same time
"""
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
    """Get current Unix timestamp in seconds."""
    return time.time()


def _jitter_minutes(key: str, max_minutes: int = 30) -> int:
    """
    Generate a deterministic jitter value (0-30 minutes) based on cache key.
    
    This ensures the same symbol always gets the same jitter value,
    preventing cache refresh times from changing randomly.
    """
    return abs(hash(key)) % (max_minutes + 1)


def _next_day_at(hour: int, minute: int, key: str) -> float:
    """
    Calculate timestamp for next day at specified hour:minute with jitter.
    
    Args:
        hour: Target hour (0-23)
        minute: Target minute (0-59)
        key: Cache key used to generate consistent jitter
    
    Returns:
        Unix timestamp for the calculated time
    """
    now = datetime.now()
    # Set target to tomorrow at specified time
    target = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    # Add deterministic jitter to spread out cache refreshes
    jitter = _jitter_minutes(key)
    return (target + timedelta(minutes=jitter)).timestamp()


def _expiry_for_provider(provider: str, key: str) -> float:
    """
    Calculate cache expiry timestamp based on provider type.
    
    Alpha Vantage: Expires at ~6:00 AM UTC (markets open)
    Stooq: Expires at ~1:00 AM UTC (overnight refresh)
    """
    if provider == "alpha":
        return _next_day_at(6, 0, key)
    return _next_day_at(1, 0, key)


def _to_dataframe(data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert raw OHLCV data to a pandas DataFrame with proper datetime index.
    
    Args:
        data: List of dicts with keys {t, o, h, l, c, v}
    
    Returns:
        DataFrame with datetime index and columns [open, high, low, close, volume]
    """
    df = pd.DataFrame(data)
    df["t"] = pd.to_datetime(df["t"])
    df = df.set_index("t").sort_index()
    # Rename to standard OHLCV column names
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    return df


def _is_insufficient(data: List[Dict[str, Any]], interval: str, chart_points: int) -> bool:
    """
    Check if fetched data is insufficient for analysis.
    
    Stooq sometimes returns incomplete data. This detects when we have
    too few recent data points for short-term analysis (< 25 days for 60-90 day window).
    
    Returns:
        True if data is insufficient and should trigger Alpha Vantage fallback
    """
    if interval not in {"1d", "daily"}:
        return False
    if chart_points > 90:
        return False
    # If requesting 60-90 points but only got < 25, data is stale/incomplete
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
    """
    Fetch stock price history with smart provider selection and caching.
    
    Provider Priority:
    1. Return valid cache if not expired (unless mode='force')
    2. Try Stooq (free, unlimited)
    3. Fall back to Alpha Vantage (quota-limited)
    4. Return stale cache if both fail
    5. Return None if no data available
    
    Args:
        symbol: Stock ticker (e.g., 'AAPL')
        stooq_symbol: Optional Stooq-specific symbol (e.g., 'aapl.us')
        interval: Time interval (only 'daily' supported; resampling done later)
        chart_points: Number of data points needed (used to detect insufficient data)
        outputsize: Alpha Vantage output size ('compact' = 100 days, 'full' = 20+ years)
        mode: 'daily' uses cache, 'force' always refreshes
        alpha_key: Alpha Vantage API key
    
    Returns:
        Tuple of (DataFrame or None, metadata dict)
        Metadata includes: provider, cache_status, fetch times, errors
    """
    cache_key = f"stock:{symbol}:daily"
    cached = get_entry(cache_key)
    now = _now()
    
    # Return valid cache if not expired and not forcing refresh
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

    # Try fetching from Stooq if cache is expired or refresh is forced
    stooq_error = None
    if mode == "force" or not cached or cached.get("expires_at", 0) <= now:
        # Attempt to fetch from Stooq (free, unlimited provider)
        data, err = fetch_stooq_daily(symbol, stooq_symbol)
        time.sleep(STOOQ_MIN_REQUEST_DELAY_SECONDS)  # Rate limiting courtesy delay
        
        # If Stooq data is good and sufficient, cache it and return
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
        
        # Track Stooq failures for diagnostics
        if data and _is_insufficient(data, interval, chart_points):
            stooq_error = "insufficient"
            record_stooq_failure()
        if err:
            stooq_error = err
            record_stooq_failure()

    # Try Alpha Vantage as fallback if Stooq failed and we're allowed to use Alpha
    alpha_allowed = mode == "force" or (not cached or cached.get("expires_at", 0) <= now)
    if alpha_allowed and alpha_key and can_use_alpha(now):
        # Wait for an available quota slot (respects rate limits)
        wait_for_alpha_slot()
        data, err = fetch_alpha_daily(symbol, alpha_key, outputsize=outputsize)
        record_provider_call("alpha", now)  # Track usage for quota management
        time.sleep(ALPHA_VANTAGE_MIN_REQUEST_INTERVAL)  # Mandatory rate limit delay
        
        if data:
            # Alpha Vantage succeeded - cache the data
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

    # Both providers failed - return stale cache if available
    if cached:
        record_request(cache_hit=True)
        return _to_dataframe(cached.get("data", [])), {
            "provider": cached.get("provider"),
            "source_symbol": cached.get("source_symbol"),
            "fetched_at": cached.get("fetched_at"),
            "expires_at": cached.get("expires_at"),
            "is_stale": True,  # Flag that this data is expired
            "cache_status": "stale",
            "stooq_error": stooq_error,
        }

    # No cache and both providers failed - return None
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
    """
    Get current API usage statistics and quotas.
    
    Returns:
        Dict with Alpha Vantage usage, cache hit rate, Stooq failure count
    """
    return usage_snapshot()
