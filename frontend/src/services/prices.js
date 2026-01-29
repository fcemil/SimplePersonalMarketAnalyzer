/**
 * Price lookup utilities for portfolio operations.
 * 
 * Provides functions to find historical prices from asset data,
 * used when entering trades with automatic price lookup.
 */

/**
 * Find the closing price on or before a specific date from asset data.
 * 
 * @param {Object} asset - Asset object with price history
 * @param {Object} asset.dates - Array of date strings (YYYY-MM-DD)
 * @param {Object} asset.series - Array of closing prices
 * @param {string} date - Target date (YYYY-MM-DD format)
 * 
 * @returns {Object} Result object with:
 *   - error: Error message if price not found
 *   - usedDate: Actual date used (may be before target if no exact match)
 *   - close: Closing price on that date
 *   - provider: Data source ('stooq', 'alpha', 'fred', 'cache')
 *   - freshness: Data freshness ('fresh' or 'stale')
 * 
 * Algorithm:
 * - Scans backwards from end of price history
 * - Returns first date <= target date
 * - Useful for "trade as of" scenarios where exact date may not have data
 */
export function getCloseOnOrBefore(asset, date) {
  // Validate input
  if (!asset || !asset.dates || !asset.series) {
    return { error: 'Missing price history' }
  }
  
  const target = new Date(`${date}T00:00:00Z`)
  const dates = asset.dates
  
  // Search backwards for first date <= target
  let idx = -1
  for (let i = dates.length - 1; i >= 0; i -= 1) {
    if (new Date(`${dates[i]}T00:00:00Z`) <= target) {
      idx = i
      break
    }
  }
  
  // No data before target date
  if (idx === -1) {
    return { error: 'No price available before selected date' }
  }
  
  // Return price and metadata
  const close = Number(asset.series[idx])
  return {
    usedDate: dates[idx],
    close,
    provider: asset.provider || asset.cache_status || 'cache',
    freshness: asset.is_stale ? 'stale' : 'fresh',
  }
}
