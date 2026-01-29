"""
Usage tracking module - Monitor API quota and cache performance.

Tracks:
- Alpha Vantage API calls (daily and per-minute limits)
- Cache hit/miss statistics
- Stooq provider failure count

This enables the system to respect free-tier API limits and provide
usage visibility to the user.
"""
import json
import os
import time
from datetime import datetime
from typing import Any, Dict

from .config import ALPHA_DAILY_BUDGET, ALPHA_PER_MINUTE_BUDGET

# Path to usage tracking JSON file
USAGE_PATH = os.getenv(
    "USAGE_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "usage.json"),
)


def _load_usage() -> Dict[str, Any]:
    """
    Load usage data from disk.
    
    Returns:
        Dict with structure:
        {
          "daily": { "alpha": { "2026-01-29": 5 } },
          "minute": { "alpha": [timestamp1, timestamp2, ...] },
          "stats": { "cache_hits": 10, "requests": 20, "stooq_failures": 2 }
        }
    """
    if not os.path.exists(USAGE_PATH):
        return {"daily": {}, "minute": {}, "stats": {"cache_hits": 0, "requests": 0, "stooq_failures": 0}}
    try:
        with open(USAGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"daily": {}, "minute": {}, "stats": {"cache_hits": 0, "requests": 0, "stooq_failures": 0}}


def _save_usage(usage: Dict[str, Any]) -> None:
    """Save usage data to disk."""
    os.makedirs(os.path.dirname(USAGE_PATH), exist_ok=True)
    with open(USAGE_PATH, "w", encoding="utf-8") as f:
        json.dump(usage, f)


def _today_key(now: float) -> str:
    """Convert Unix timestamp to date string (YYYY-MM-DD)."""
    return datetime.fromtimestamp(now).strftime("%Y-%m-%d")


def record_request(cache_hit: bool) -> None:
    """
    Record a data request (cache hit or miss).
    
    Args:
        cache_hit: True if served from cache, False if fetched from provider
    """
    usage = _load_usage()
    usage["stats"]["requests"] = usage["stats"].get("requests", 0) + 1
    if cache_hit:
        usage["stats"]["cache_hits"] = usage["stats"].get("cache_hits", 0) + 1
    _save_usage(usage)


def record_stooq_failure() -> None:
    """Record a Stooq provider failure for diagnostics."""
    usage = _load_usage()
    usage["stats"]["stooq_failures"] = usage["stats"].get("stooq_failures", 0) + 1
    _save_usage(usage)


def record_provider_call(provider: str, now: float) -> None:
    """
    Record an API call to a provider for quota tracking.
    
    Tracks both daily count and per-minute count (sliding window).
    
    Args:
        provider: Provider name ('alpha', 'fred', etc.)
        now: Current Unix timestamp
    """
    usage = _load_usage()
    # Increment daily count
    daily = usage.setdefault("daily", {}).setdefault(provider, {})
    day_key = _today_key(now)
    daily[day_key] = daily.get(day_key, 0) + 1
    # Track minute-level timestamps (keep only last 60 seconds)
    minute = usage.setdefault("minute", {}).setdefault(provider, [])
    minute.append(now)
    usage["minute"][provider] = [ts for ts in minute if now - ts <= 60]
    _save_usage(usage)


def alpha_used_today(now: float) -> int:
    """Get number of Alpha Vantage API calls made today."""
    usage = _load_usage()
    day_key = _today_key(now)
    return int(usage.get("daily", {}).get("alpha", {}).get(day_key, 0))


def alpha_calls_last_minute(now: float) -> int:
    """Get number of Alpha Vantage API calls in the last 60 seconds."""
    usage = _load_usage()
    minute = usage.get("minute", {}).get("alpha", [])
    return len([ts for ts in minute if now - ts <= 60])


def can_use_alpha(now: float) -> bool:
    """
    Check if we can make an Alpha Vantage API call without exceeding quota.
    
    Respects both daily budget and per-minute rate limit.
    """
    if alpha_used_today(now) >= ALPHA_DAILY_BUDGET:
        return False
    if alpha_calls_last_minute(now) >= ALPHA_PER_MINUTE_BUDGET:
        return False
    return True


def wait_for_alpha_slot() -> None:
    """
    Wait until an Alpha Vantage API call slot is available.
    
    Blocks until the per-minute rate limit allows another call.
    If daily budget is exhausted, returns immediately (caller should check can_use_alpha first).
    """
    while True:
        now = time.time()
        # If daily budget exhausted, give up
        if alpha_used_today(now) >= ALPHA_DAILY_BUDGET:
            return
        # Check per-minute limit
        minute = _load_usage().get("minute", {}).get("alpha", [])
        minute = [ts for ts in minute if now - ts <= 60]
        if len(minute) < ALPHA_PER_MINUTE_BUDGET:
            return
        # Calculate how long to wait for oldest call to age out
        oldest = min(minute)
        sleep_for = max(0.1, 60 - (now - oldest))
        time.sleep(sleep_for)


def usage_snapshot() -> Dict[str, Any]:
    """
    Get current usage statistics for display.
    
    Returns:
        Dict with alpha quota usage, cache hit rate, and Stooq failures
    """
    now = time.time()
    usage = _load_usage()
    stats = usage.get("stats", {})
    requests = stats.get("requests", 0)
    cache_hits = stats.get("cache_hits", 0)
    hit_rate = (cache_hits / requests) if requests else 0
    return {
        "alpha": {
            "usedToday": alpha_used_today(now),
            "budget": ALPHA_DAILY_BUDGET,
            "usedLastMinute": alpha_calls_last_minute(now),
        },
        "cache": {"hitRate": hit_rate},
        "stooq": {"failures": stats.get("stooq_failures", 0)},
    }
