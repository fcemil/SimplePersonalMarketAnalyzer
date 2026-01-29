"""
Configuration module - Centralized app settings.

Defines:
- API keys (loaded from environment)
- Default watchlist stocks
- Commodity data sources (FRED series IDs)
- Analysis parameters (window sizes, thresholds)
- Cache and rate limit settings
"""
import os

# API keys (set as environment variables or in a .env file)
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# Simple curated universe; update as you like
# These are used as default watchlist if user hasn't created one
POPULAR_STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA",
    "BRK.B", "JPM", "XOM", "UNH", "V", "MA",
    "GLD", "SLV",  # Gold and silver ETFs
]

# Commodities via FRED series IDs (daily series where available)
# Source: Federal Reserve Economic Data (FRED)
POPULAR_COMMODITIES = {
    "WTI Crude": {"source": "fred", "series_id": "DCOILWTICO"},
    "Brent Crude": {"source": "fred", "series_id": "DCOILBRENTEU"},
    "Natural Gas": {"source": "fred", "series_id": "DHHNGSP"},
}

# Analysis settings
ANALYSIS_WINDOW_DAYS = 30  # Window for return and volatility calculations
DRAWDOWN_WINDOW_DAYS = 63  # ~3 months for drawdown calculation
TRADING_DAYS_IN_MONTH = ANALYSIS_WINDOW_DAYS

# Cache + provider settings
CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours (not actively used; see asset_manager for actual expiry logic)
ALPHA_VANTAGE_MIN_REQUEST_INTERVAL = 1.1  # Minimum seconds between Alpha API calls
ALPHA_DAILY_BUDGET = 10  # Max Alpha calls per day (free tier allows 25, using 10 for safety)
ALPHA_PER_MINUTE_BUDGET = 5  # Max Alpha calls per minute
STOOQ_DAILY_BUDGET = 9999  # Stooq is unlimited, but good to track
STOOQ_MIN_REQUEST_DELAY_SECONDS = 0.2  # Courtesy delay between Stooq requests
DAILY_REFRESH_TIME = "08:30"  # Suggested refresh time (not enforced server-side)
