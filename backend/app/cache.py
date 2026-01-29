import json
import os
import time
from typing import Any, Optional

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cache.json")


def _load_cache() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def get_cache(key: str, ttl_seconds: int) -> Optional[Any]:
    cache = _load_cache()
    entry = cache.get(key)
    if not entry:
        return None
    if time.time() - entry.get("timestamp", 0) > ttl_seconds:
        return None
    return entry.get("data")


def set_cache(key: str, data: Any) -> None:
    cache = _load_cache()
    cache[key] = {"timestamp": time.time(), "data": data}
    _save_cache(cache)
