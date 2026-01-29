"""
Asset Cache module - Persistent JSON storage for asset price data.

Stores fetched asset data with expiry times to reduce API calls.
Each cache entry includes:
- provider: Data source ('stooq', 'alpha', 'fred')
- fetched_at: Timestamp when data was fetched
- expires_at: Timestamp when cache should be refreshed
- data: List of OHLCV records
"""
import json
import os
from typing import Any, Dict, Optional

# Path to the asset cache JSON file
ASSET_CACHE_PATH = os.getenv(
    "ASSET_CACHE_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "asset_cache.json"),
)


def _load_cache() -> Dict[str, Any]:
    """
    Load the entire cache from disk.
    
    Returns:
        Dict mapping cache keys to entry dicts
    """
    if not os.path.exists(ASSET_CACHE_PATH):
        return {}
    try:
        with open(ASSET_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    """Save the entire cache to disk."""
    os.makedirs(os.path.dirname(ASSET_CACHE_PATH), exist_ok=True)
    with open(ASSET_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def get_entry(key: str) -> Optional[Dict[str, Any]]:
    """
    Get a cache entry by key.
    
    Args:
        key: Cache key (e.g., 'stock:AAPL:daily')
    
    Returns:
        Cache entry dict or None if not found
    """
    return _load_cache().get(key)


def set_entry(key: str, entry: Dict[str, Any]) -> None:
    """
    Store or update a cache entry.
    
    Args:
        key: Cache key
        entry: Entry data to store
    """
    cache = _load_cache()
    cache[key] = entry
    _save_cache(cache)
