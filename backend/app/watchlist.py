import json
import os
from typing import List

from .config import POPULAR_STOCKS

WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "watchlist.json")


def load_watchlist() -> List[str]:
    if not os.path.exists(WATCHLIST_PATH):
        return [s.upper() for s in POPULAR_STOCKS]
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("stocks", [])
        return [str(s).upper() for s in items if s]
    except (json.JSONDecodeError, OSError):
        return [s.upper() for s in POPULAR_STOCKS]


def save_watchlist(stocks: List[str]) -> None:
    os.makedirs(os.path.dirname(WATCHLIST_PATH), exist_ok=True)
    payload = {"stocks": sorted(set([s.upper() for s in stocks]))}
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def add_symbol(symbol: str) -> List[str]:
    symbol = symbol.strip().upper()
    if not symbol:
        return load_watchlist()
    items = load_watchlist()
    if symbol not in items:
        items.append(symbol)
    save_watchlist(items)
    return items


def remove_symbol(symbol: str) -> List[str]:
    symbol = symbol.strip().upper()
    items = [s for s in load_watchlist() if s != symbol]
    save_watchlist(items)
    return items
