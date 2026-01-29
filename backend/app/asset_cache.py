import json
import os
from typing import Any, Dict, Optional

ASSET_CACHE_PATH = os.getenv(
    "ASSET_CACHE_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "asset_cache.json"),
)


def _load_cache() -> Dict[str, Any]:
    if not os.path.exists(ASSET_CACHE_PATH):
        return {}
    try:
        with open(ASSET_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(ASSET_CACHE_PATH), exist_ok=True)
    with open(ASSET_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def get_entry(key: str) -> Optional[Dict[str, Any]]:
    return _load_cache().get(key)


def set_entry(key: str, entry: Dict[str, Any]) -> None:
    cache = _load_cache()
    cache[key] = entry
    _save_cache(cache)
