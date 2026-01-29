"""
Data providers module for MarketAnalyzer.

This module handles fetching historical and real-time market data from multiple sources:
- Stooq (primary source for daily historical data, free and cached locally)
- Alpha Vantage (fallback for daily data and quotes, quota-limited free tier)
- FRED (Federal Reserve Economic Data for commodities)

Key features:
- Symbol format conversion for different exchanges (Stooq format)
- Currency inference based on exchange suffix
- Local file-based caching to minimize API calls
- Data resampling from daily to weekly/monthly intervals
- Graceful fallback when providers fail or quotas are exceeded
"""

import csv
import io
import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd
import requests

# Directory where cached market data CSV files are stored
# Cache reduces API calls and provides historical data when providers are unavailable
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")


def _ensure_cache_dir() -> None:
    """
    Ensure the cache directory exists, creating it if necessary.
    
    This is called before writing any cache files to prevent file system errors.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)


def _stooq_symbol(symbol: str) -> str:
    """
    Convert a symbol to Stooq format.
    
    Stooq requires specific suffixes for different exchanges:
    - .us = US stocks (NASDAQ, NYSE)
    - .uk/.lon = London Stock Exchange
    - .de = Frankfurt/XETRA
    - .to/.trt/.trv = Toronto Stock Exchange
    - .pa = Paris (Euronext)
    - .as = Amsterdam
    - .sw = Switzerland
    - .mi = Milan
    - .hk = Hong Kong
    - .ss/.sz = Shanghai/Shenzhen
    
    Note: .sh suffix is not recognized by Stooq's format but is used in currency inference.
    
    For symbols without a recognized suffix, defaults to .us market.
    Also converts "." to "-" in ticker symbols (e.g., BRK.B → BRK-B).
    
    Args:
        symbol: The input symbol (e.g., "AAPL", "MSFT.US", "VOD.LON")
        
    Returns:
        Symbol formatted for Stooq API (lowercase with appropriate suffix)
    """
    base = symbol.lower()
    # If symbol already has a recognized exchange suffix, use as-is
    if base.endswith(
        (
            ".us",
            ".uk",
            ".de",
            ".to",
            ".trt",
            ".trv",
            ".lon",
            ".as",
            ".pa",
            ".sw",
            ".mi",
            ".hk",
            ".ss",
            ".sz",
        )
    ):
        return base
    # Otherwise, convert dots to dashes and append .us (default to US market)
    return base.replace(".", "-") + ".us"


def infer_currency(symbol: str, asset_type: str) -> str:
    """
    Infer the currency for an asset based on its symbol and type.
    
    Currency inference rules:
    - Commodities always use USD (global standard)
    - Exchange suffix determines currency:
      * .us = USD (US exchanges)
      * .uk/.lon = GBP (London)
      * .de/.dex/.xetra/.fr/.pa/.mi/.as = EUR (European exchanges)
      * .to/.trt/.trv = CAD (Toronto)
      * .sw = CHF (Switzerland)
      * .hk = HKD (Hong Kong)
      * .ss/.sh/.sz = CNY (Chinese exchanges)
    - Default to USD if no recognized suffix
    
    Args:
        symbol: The asset symbol (e.g., "AAPL", "VOD.LON")
        asset_type: Type of asset ("stock", "commodity", etc.)
        
    Returns:
        Three-letter currency code (ISO 4217)
    """
    # Commodities are globally traded in USD
    if asset_type == "commodity":
        return "USD"
    base = symbol.lower()
    # Match exchange suffix to currency
    if base.endswith(".us"):
        return "USD"
    if base.endswith((".uk", ".lon")):
        return "GBP"
    if base.endswith((".de", ".dex", ".xetra", ".fr", ".pa", ".mi", ".as")):
        return "EUR"
    if base.endswith((".to", ".trt", ".trv")):
        return "CAD"
    if base.endswith(".sw"):
        return "CHF"
    if base.endswith(".hk"):
        return "HKD"
    if base.endswith((".ss", ".sh", ".sz")):
        return "CNY"
    # Default to USD for unknown or US stocks without suffix
    return "USD"


def _cache_path(symbol: str) -> str:
    """
    Generate the file system path for a symbol's cache file.
    
    Converts symbol to a safe filename by:
    - Converting to uppercase for consistency
    - Replacing "/" with "_" (for forex pairs like EUR/USD)
    - Replacing "." with "-" (for class shares like BRK.B)
    
    Args:
        symbol: The asset symbol
        
    Returns:
        Full path to the cache CSV file
    """
    safe = symbol.upper().replace("/", "_").replace(".", "-")
    return os.path.join(CACHE_DIR, f"stooq_{safe}.csv")


def _read_cache(symbol: str) -> Optional[pd.DataFrame]:
    """
    Read cached historical data for a symbol from disk.
    
    Cache files are CSV format with a Date column that becomes the index.
    Returns None if cache doesn't exist or is malformed.
    
    Args:
        symbol: The asset symbol to read from cache
        
    Returns:
        DataFrame with Date index and OHLCV columns, or None if cache miss
    """
    path = _cache_path(symbol)
    # Return None if no cached data exists
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    # Validate that cache file has required Date column
    if "Date" not in df.columns:
        return None
    # Parse dates and set as index for time-series operations
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    return df


def _write_cache(symbol: str, df: pd.DataFrame) -> None:
    """
    Write historical data to cache file on disk.
    
    Ensures cache directory exists before writing.
    Resets the Date index to a column for CSV storage.
    
    Args:
        symbol: The asset symbol
        df: DataFrame with Date index and OHLCV data to cache
    """
    _ensure_cache_dir()
    path = _cache_path(symbol)
    # Reset index to save Date as a column in CSV
    df = df.reset_index()
    df.to_csv(path, index=False)


def fetch_stooq_daily(symbol: str, stooq_symbol: Optional[str] = None) -> Tuple[Optional[List[dict]], Optional[str]]:
    """
    Fetch daily historical data from Stooq API.
    
    Stooq is a free data provider (no API key needed) that provides historical
    stock prices from global exchanges. This is the primary data source for the app.
    
    Data format returned:
    - List of dicts with keys: t (date), o (open), h (high), l (low), c (close), v (volume)
    
    Args:
        symbol: The asset symbol to fetch
        stooq_symbol: Optional pre-formatted Stooq symbol (bypasses _stooq_symbol conversion)
        
    Returns:
        Tuple of (data_list, error_string):
        - (list_of_dicts, None) on success
        - (None, "network") on HTTP error
        - (None, "symbol_not_found") if symbol doesn't exist
        - (None, "malformed") if data is invalid
    """
    # Convert symbol to Stooq format unless already provided
    stooq_code = (stooq_symbol or _stooq_symbol(symbol)).lower()
    params = {"s": stooq_code, "i": "d"}  # i=d requests daily data frequency
    url = "https://stooq.com/q/d/l/"
    response = requests.get(url, params=params, timeout=20)
    # Check for network/HTTP errors
    if not response.ok:
        return None, "network"
    text = response.text.strip()
    # Stooq returns "No data" text when symbol is invalid or delisted
    if not text or text.lower().startswith("no data"):
        return None, "symbol_not_found"
    # Parse CSV response
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        # Skip empty or malformed rows
        if not row or not row.get("Date"):
            continue
        rows.append(row)
    if not rows:
        return None, "symbol_not_found"
    # Convert CSV rows to standardized format
    parsed = []
    for row in rows:
        try:
            # Map Stooq columns to our internal format (t, o, h, l, c, v)
            parsed.append(
                {
                    "t": row["Date"],
                    "o": float(row.get("Open") or 0),
                    "h": float(row.get("High") or 0),
                    "l": float(row.get("Low") or 0),
                    "c": float(row.get("Close") or 0),
                    "v": float(row.get("Volume") or 0),
                }
            )
        except (TypeError, ValueError):
            # Skip rows with invalid numeric data
            continue
    if not parsed:
        return None, "malformed"
    # Sort by date to ensure chronological order
    parsed.sort(key=lambda x: x["t"])
    return parsed, None


def fetch_alpha_daily(symbol: str, api_key: str, outputsize: str = "compact") -> Tuple[Optional[List[dict]], Optional[str]]:
    """
    Fetch daily adjusted historical data from Alpha Vantage API.
    
    Alpha Vantage is a fallback provider when Stooq fails. Free tier is limited to:
    - 25 requests per day
    - 5 requests per minute
    
    This function is used sparingly to respect quota limits.
    
    Args:
        symbol: The asset symbol (use original format, not Stooq format)
        api_key: Alpha Vantage API key
        outputsize: "compact" (last 100 days) or "full" (20+ years)
        
    Returns:
        Tuple of (data_list, error_string):
        - (list_of_dicts, None) on success
        - (None, error_message) on failure (includes quota exceeded messages)
    """
    if not api_key:
        return None, "ALPHA_VANTAGE_KEY not set"
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",  # Includes splits and dividends
        "symbol": symbol,
        "apikey": api_key,
        "outputsize": outputsize,
    }
    response = requests.get(url, params=params, timeout=20)
    if not response.ok:
        return None, f"HTTP {response.status_code}"
    payload = response.json()
    # Find the time series data (key name varies by function)
    series = None
    for key, value in payload.items():
        if isinstance(key, str) and key.startswith("Time Series"):
            series = value
            break
    if not series:
        # Alpha Vantage returns errors in various fields
        reason = payload.get("Note") or payload.get("Error Message") or payload.get("Information")
        return None, reason or "Missing time series"
    # Parse the time series data
    parsed = []
    for date_str, values in series.items():
        try:
            # Map Alpha Vantage field names to our internal format
            # Note: field "6. volume" is preferred, "5. volume" is fallback
            parsed.append(
                {
                    "t": date_str,
                    "o": float(values.get("1. open") or 0),
                    "h": float(values.get("2. high") or 0),
                    "l": float(values.get("3. low") or 0),
                    "c": float(values.get("4. close") or 0),
                    "v": float(values.get("6. volume") or values.get("5. volume") or 0),
                }
            )
        except (TypeError, ValueError):
            # Skip malformed data points
            continue
    if not parsed:
        return None, "Malformed Alpha Vantage response"
    # Sort chronologically
    parsed.sort(key=lambda x: x["t"])
    return parsed, None


def _fetch_stooq(symbol: str, start: Optional[datetime], end: Optional[datetime]) -> pd.DataFrame:
    """
    Internal helper to fetch Stooq data as a pandas DataFrame.
    
    Supports optional date range filtering for incremental cache updates.
    Returns data with lowercase column names (open, high, low, close, volume).
    
    Args:
        symbol: Asset symbol to fetch
        start: Optional start date for date range query
        end: Optional end date for date range query
        
    Returns:
        DataFrame with Date index and OHLCV columns
        
    Raises:
        HTTPError: If Stooq returns non-200 status
        ValueError: If response format is unexpected
    """
    params = {"s": _stooq_symbol(symbol), "i": "d"}
    # Add date range parameters if provided (format: YYYYMMDD)
    if start and end:
        params["d1"] = start.strftime("%Y%m%d")
        params["d2"] = end.strftime("%Y%m%d")
    url = "https://stooq.com/q/d/l/"
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    # Parse CSV response directly into DataFrame
    df = pd.read_csv(io.StringIO(response.text))
    if "Date" not in df.columns:
        raise ValueError("Unexpected Stooq response")
    # Convert Date column to datetime and use as index
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    # Standardize column names to lowercase for consistency
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    return df


def get_history(symbol: str, refresh: bool) -> pd.DataFrame:
    """
    Get historical daily data for a symbol, using cache when possible.
    
    Caching behavior:
    - If no cache exists: fetch full history from Stooq and cache it
    - If cache exists and refresh=False: return cached data (no API call)
    - If cache exists and refresh=True: fetch only new data since last cached date
    
    This incremental update strategy minimizes API calls while keeping data current.
    If refresh fails (network error, API down), returns cached data as fallback.
    
    Args:
        symbol: Asset symbol to fetch
        refresh: Whether to fetch new data or use cache
        
    Returns:
        DataFrame with Date index and OHLCV columns (open, high, low, close, volume)
    """
    cached = _read_cache(symbol)
    # No cache exists: fetch full history and cache it
    if cached is None or cached.empty:
        df = _fetch_stooq(symbol, None, None)
        _write_cache(symbol, df)
        return df

    # Cache exists but refresh not requested: return cached data
    if not refresh:
        return cached

    # Refresh requested: fetch only new data since last cached date
    last_date = cached.index.max()
    start = last_date + timedelta(days=1)  # Start from day after last cached date
    end = datetime.utcnow()
    # If cache is already up-to-date, return it
    if start.date() > end.date():
        return cached

    # Attempt to fetch new data
    try:
        new_data = _fetch_stooq(symbol, start, end)
    except Exception:
        # If fetch fails (network, API down), return cached data as fallback
        return cached
    if new_data.empty:
        return cached

    # Merge new data with cache
    combined = pd.concat([cached, new_data]).sort_index()
    # Remove duplicates, keeping the most recent data (from new_data)
    combined = combined[~combined.index.duplicated(keep="last")]
    # Update cache with merged data
    _write_cache(symbol, combined)
    return combined


def latest_from_history(df: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract the latest price and daily change from historical data.
    
    Used to get current price when real-time quote APIs are unavailable
    or to avoid unnecessary API calls.
    
    Args:
        df: DataFrame with historical data (Date index, close column required)
        
    Returns:
        Tuple of (latest_price, daily_change_pct):
        - latest_price: Most recent closing price
        - daily_change_pct: Percentage change from previous close (e.g., 0.05 = +5%)
        - Returns (None, None) if data is empty or invalid
    """
    if df is None or df.empty:
        return None, None
    # Get most recent close price
    latest = float(df["close"].iloc[-1])
    # Get previous close for change calculation (if available)
    prev = float(df["close"].iloc[-2]) if len(df) > 1 else None
    change = None
    if prev and prev != 0:
        # Calculate percentage change: (current / previous) - 1
        change = (latest / prev) - 1
    return latest, change


def resample_history(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """
    Resample daily data to weekly or monthly intervals.
    
    Resampling rules:
    - Daily: return as-is (no resampling)
    - Weekly: resample to week-ending Friday (W-FRI)
    - Monthly: resample to month-end (M)
    
    OHLCV aggregation:
    - Open: first value of period
    - High: maximum value of period
    - Low: minimum value of period
    - Close: last value of period
    - Volume: sum of period volumes
    
    This local resampling eliminates the need for weekly/monthly data from providers,
    saving API quota and reducing dependency on external services.
    
    Args:
        df: DataFrame with daily data (Date index, OHLCV columns)
        interval: "1d"/"daily", "1w"/"weekly", or "1m"/"monthly"
        
    Returns:
        Resampled DataFrame with same column structure
    """
    # No resampling needed for daily data
    if interval in {"1d", "daily"}:
        return df
    # Determine pandas resample rule
    if interval in {"1w", "weekly"}:
        rule = "W-FRI"  # Week ending on Friday
    elif interval in {"1m", "monthly"}:
        rule = "M"  # Month end
    else:
        return df  # Unknown interval, return as-is

    # Ensure required OHLC columns exist (backfill from close if missing)
    if {"open", "high", "low"}.issubset(df.columns) is False:
        df = df.copy()
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"] = df["close"]
    # Ensure volume column exists (default to 0 if missing)
    if "volume" not in df.columns:
        df = df.copy()
        df["volume"] = 0

    # Define aggregation rules for each OHLCV column
    agg = {
        "open": "first",   # Opening price = first day's open
        "high": "max",     # High = highest high in period
        "low": "min",      # Low = lowest low in period
        "close": "last",   # Close = last day's close
        "volume": "sum",   # Volume = sum of all days' volume
    }
    # Resample and drop periods with no close price (weekends, holidays)
    resampled = df.resample(rule).agg(agg).dropna(subset=["close"])
    return resampled


def fetch_alpha_quote(symbol: str, api_key: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Fetch real-time quote from Alpha Vantage GLOBAL_QUOTE endpoint.
    
    This is a lightweight alternative to full historical data fetch.
    Used when only the current price is needed (e.g., portfolio valuation).
    
    Note: Still counts against Alpha Vantage's 25 req/day quota, so use sparingly.
    Consider using latest_from_history() instead when historical data is already available.
    
    Args:
        symbol: Asset symbol to quote
        api_key: Alpha Vantage API key
        
    Returns:
        Tuple of (current_price, daily_change_pct):
        - current_price: Latest trading price
        - daily_change_pct: Percentage change from previous close
        - Returns (None, None) on failure or if API key is missing
    """
    if not api_key:
        return None, None
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",  # Lightweight quote endpoint
        "symbol": symbol,
        "apikey": api_key,
    }
    response = requests.get(url, params=params, timeout=20)
    if not response.ok:
        return None, None
    payload = response.json()
    # Extract quote data from response
    quote = payload.get("Global Quote") or {}
    price = quote.get("05. price")
    prev = quote.get("08. previous close")
    # Parse price safely
    try:
        latest = float(price)
    except (TypeError, ValueError):
        latest = None
    # Parse previous close safely
    try:
        prev_close = float(prev)
    except (TypeError, ValueError):
        prev_close = None
    # Calculate percentage change
    change = None
    if latest is not None and prev_close:
        change = (latest / prev_close) - 1
    return latest, change
