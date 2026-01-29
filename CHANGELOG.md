# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Added
- Home / Analyze / Portfolio / Simulation pages with Vue Router navigation.
- Hybrid data pipeline: Stooq daily candles (primary), Alpha Vantage fallback with budgets, and usage stats.
- Charting upgrades: lightweight-charts core, SMA/EMA/BB overlays, RSI/MACD/Volume panels, fullscreen, and drawing tools.
- Portfolio MVP with auto price lookup, auto fees, auto quantity, and WAC positions.
- Local settings for fee policy and quantity precision.
- Quota usage widget and provider freshness badges.

### Changed
- Analysis window is now 30 trading days with 3‑month drawdown labeling.
- Asset payloads now include provider metadata, cache status, and sample counts.
- Cache storage moved to `backend/data/asset_cache.json` with provider-specific TTLs.

### Fixed
- Stooq/Alpha fallback now handles insufficient history by switching providers.
