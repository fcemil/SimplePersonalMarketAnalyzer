import importlib
import time


def _sample_data(count=30):
    base = 1700000000
    data = []
    for i in range(count):
        day = time.strftime("%Y-%m-%d", time.gmtime(base + i * 86400))
        data.append({"t": day, "o": 100 + i, "h": 101 + i, "l": 99 + i, "c": 100 + i, "v": 1000})
    return data


def _reload_modules(monkeypatch, tmp_path):
    monkeypatch.setenv("ASSET_CACHE_PATH", str(tmp_path / "asset_cache.json"))
    monkeypatch.setenv("USAGE_PATH", str(tmp_path / "usage.json"))
    from backend.app import asset_cache, usage, asset_manager
    importlib.reload(asset_cache)
    importlib.reload(usage)
    importlib.reload(asset_manager)
    return asset_cache, usage, asset_manager


def test_repeat_refresh_uses_cache(monkeypatch, tmp_path):
    asset_cache, usage, asset_manager = _reload_modules(monkeypatch, tmp_path)
    calls = {"stooq": 0}
    monkeypatch.setattr(asset_manager.time, "sleep", lambda *_: None)

    def fake_stooq(symbol, stooq_symbol=None):
        calls["stooq"] += 1
        return _sample_data(), None

    monkeypatch.setattr(asset_manager, "fetch_stooq_daily", fake_stooq)
    df, meta = asset_manager.fetch_stock_history(
        symbol="AAPL",
        stooq_symbol="aapl.us",
        interval="1d",
        chart_points=60,
        outputsize="compact",
        mode="daily",
        alpha_key="demo",
    )
    assert calls["stooq"] == 1
    for _ in range(20):
        df, meta = asset_manager.fetch_stock_history(
            symbol="AAPL",
            stooq_symbol="aapl.us",
            interval="1d",
            chart_points=60,
            outputsize="compact",
            mode="daily",
            alpha_key="demo",
        )
    assert calls["stooq"] == 1


def test_stooq_down_alpha_budget_then_stale(monkeypatch, tmp_path):
    asset_cache, usage, asset_manager = _reload_modules(monkeypatch, tmp_path)
    monkeypatch.setattr(asset_manager.time, "sleep", lambda *_: None)

    def fake_stooq(symbol, stooq_symbol=None):
        return None, "network"

    def fake_alpha(symbol, api_key, outputsize="compact"):
        return _sample_data(), None

    monkeypatch.setattr(asset_manager, "fetch_stooq_daily", fake_stooq)
    monkeypatch.setattr(asset_manager, "fetch_alpha_daily", fake_alpha)
    usage.ALPHA_DAILY_BUDGET = 1

    df, meta = asset_manager.fetch_stock_history(
        symbol="AAPL",
        stooq_symbol="aapl.us",
        interval="1d",
        chart_points=60,
        outputsize="compact",
        mode="daily",
        alpha_key="demo",
    )
    assert meta["provider"] == "alpha"
    entry = asset_cache.get_entry("stock:AAPL:daily")
    entry["expires_at"] = time.time() - 10
    asset_cache.set_entry("stock:AAPL:daily", entry)

    df, meta = asset_manager.fetch_stock_history(
        symbol="AAPL",
        stooq_symbol="aapl.us",
        interval="1d",
        chart_points=60,
        outputsize="compact",
        mode="daily",
        alpha_key="demo",
    )
    assert meta["is_stale"] is True


def test_symbol_mapping_prompt(monkeypatch, tmp_path):
    asset_cache, usage, asset_manager = _reload_modules(monkeypatch, tmp_path)
    monkeypatch.setattr(asset_manager.time, "sleep", lambda *_: None)

    def fake_stooq(symbol, stooq_symbol=None):
        if stooq_symbol == "aapl.us":
            return _sample_data(), None
        return None, "symbol_not_found"

    monkeypatch.setattr(asset_manager, "fetch_stooq_daily", fake_stooq)

    df, meta = asset_manager.fetch_stock_history(
        symbol="AAPL",
        stooq_symbol=None,
        interval="1d",
        chart_points=60,
        outputsize="compact",
        mode="daily",
        alpha_key="",
    )
    assert meta.get("stooq_error") == "symbol_not_found"

    df, meta = asset_manager.fetch_stock_history(
        symbol="AAPL",
        stooq_symbol="aapl.us",
        interval="1d",
        chart_points=60,
        outputsize="compact",
        mode="daily",
        alpha_key="",
    )
    assert meta["provider"] == "stooq"
