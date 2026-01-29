import os

# API keys (set as environment variables or in a .env file)
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# Simple curated universe; update as you like
POPULAR_STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA",
    "BRK.B", "JPM", "XOM", "UNH", "V", "MA",
    "GLD", "SLV",
]

# Commodities via FRED series IDs (daily series where available)
POPULAR_COMMODITIES = {
    "WTI Crude": {"source": "fred", "series_id": "DCOILWTICO"},
    "Brent Crude": {"source": "fred", "series_id": "DCOILBRENTEU"},
    "Natural Gas": {"source": "fred", "series_id": "DHHNGSP"},
}

# Analysis settings
ANALYSIS_WINDOW_DAYS = 30
DRAWDOWN_WINDOW_DAYS = 63
TRADING_DAYS_IN_MONTH = ANALYSIS_WINDOW_DAYS

# Cache + provider settings
CACHE_TTL_SECONDS = 6 * 60 * 60
ALPHA_VANTAGE_MIN_REQUEST_INTERVAL = 1.1
ALPHA_DAILY_BUDGET = 10
ALPHA_PER_MINUTE_BUDGET = 5
STOOQ_DAILY_BUDGET = 9999
STOOQ_MIN_REQUEST_DELAY_SECONDS = 0.2
DAILY_REFRESH_TIME = "08:30"
