/**
 * Technical Indicators Module
 * 
 * Provides calculations for common technical analysis indicators used in financial charting.
 * All functions operate on price arrays and return arrays of the same length, with null values
 * for positions where the indicator cannot be calculated (e.g., during warm-up period).
 * 
 * Indicators included:
 * - SMA (Simple Moving Average)
 * - EMA (Exponential Moving Average)
 * - BB (Bollinger Bands)
 * - RSI (Relative Strength Index)
 * - MACD (Moving Average Convergence Divergence)
 */

/**
 * Computes Simple Moving Average (SMA) over a sliding window.
 * 
 * SMA is the arithmetic mean of the last N values:
 * SMA = (P₁ + P₂ + ... + Pₙ) / N
 * 
 * This implementation uses a rolling sum for O(n) time complexity instead of
 * recalculating the entire sum at each position.
 * 
 * @param values - Array of price values (typically closing prices)
 * @param period - Number of periods to average (window size)
 * @returns Array with SMA values; null for positions before period is complete
 * 
 * @example
 * computeSMA([1, 2, 3, 4, 5], 3) → [null, null, 2, 3, 4]
 */
export function computeSMA(values: number[], period: number) {
  const result: (number | null)[] = new Array(values.length).fill(null)
  let sum = 0
  for (let i = 0; i < values.length; i += 1) {
    sum += values[i] // Add current value to rolling sum
    if (i >= period) sum -= values[i - period] // Remove oldest value from window
    if (i >= period - 1) result[i] = sum / period // Calculate average when window is full
  }
  return result
}

/**
 * Computes Exponential Moving Average (EMA) with exponential weighting.
 * 
 * EMA gives more weight to recent prices than older prices using an exponential decay.
 * Formula: EMA = Price × k + EMA_prev × (1 - k)
 * where k = 2 / (period + 1) is the smoothing factor
 * 
 * EMA reacts faster to price changes than SMA because recent data has higher weight.
 * 
 * @param values - Array of price values (typically closing prices)
 * @param period - Number of periods for the EMA calculation (determines smoothing)
 * @returns Array with EMA values; null for positions before period is complete
 * 
 * @example
 * computeEMA([22, 24, 23, 25, 27], 3) → [null, null, 23, 24, 25.5]
 */
export function computeEMA(values: number[], period: number) {
  const result: (number | null)[] = new Array(values.length).fill(null)
  const k = 2 / (period + 1) // Smoothing factor: determines weight of current vs previous
  let ema = values[0] // Initialize EMA with first value
  for (let i = 0; i < values.length; i += 1) {
    // Calculate exponentially weighted average
    ema = i === 0 ? values[0] : values[i] * k + ema * (1 - k)
    if (i >= period - 1) result[i] = ema // Only output after warm-up period
  }
  return result
}

/**
 * Computes Bollinger Bands - a volatility indicator with upper and lower bands.
 * 
 * Bollinger Bands consist of three lines:
 * - Middle Band: Simple Moving Average (SMA)
 * - Upper Band: SMA + (multiplier × standard deviation)
 * - Lower Band: SMA - (multiplier × standard deviation)
 * 
 * Standard deviation measures price volatility. When volatility increases, bands widen.
 * Standard deviation formula: σ = √(Σ(x - μ)² / N)
 * 
 * Typical parameters: period=20, multiplier=2
 * 
 * @param values - Array of price values (typically closing prices)
 * @param period - Number of periods for SMA and standard deviation calculation
 * @param mult - Multiplier for standard deviation (typically 2)
 * @returns Object with {middle, upper, lower} band arrays
 * 
 * @example
 * computeBB([10, 12, 11, 13, 12], 3, 2) → {middle: [null, null, 11, 12, 12], upper: [...], lower: [...]}
 */
export function computeBB(values: number[], period: number, mult: number) {
  const middle = computeSMA(values, period) // Middle band is the SMA
  const upper: (number | null)[] = new Array(values.length).fill(null)
  const lower: (number | null)[] = new Array(values.length).fill(null)
  
  for (let i = period - 1; i < values.length; i += 1) {
    const window = values.slice(i - period + 1, i + 1) // Get values in current window
    const mean = middle[i] ?? 0
    
    // Calculate variance: average of squared differences from mean
    const variance = window.reduce((acc, v) => acc + Math.pow(v - mean, 2), 0) / period
    const sd = Math.sqrt(variance) // Standard deviation is square root of variance
    
    // Bands are SMA ± (multiplier × standard deviation)
    upper[i] = mean + mult * sd
    lower[i] = mean - mult * sd
  }
  return { middle, upper, lower }
}

/**
 * Computes Relative Strength Index (RSI) - a momentum oscillator (0-100 range).
 * 
 * RSI measures the magnitude of recent price changes to evaluate overbought or oversold conditions.
 * 
 * Calculation steps:
 * 1. Calculate price changes (gain/loss) for each period
 * 2. Average gains and losses over the period (using smoothed moving average)
 * 3. RS (Relative Strength) = Average Gain / Average Loss
 * 4. RSI = 100 - (100 / (1 + RS))
 * 
 * Interpretation:
 * - RSI > 70: Potentially overbought
 * - RSI < 30: Potentially oversold
 * - RSI = 50: Neutral
 * 
 * Typical period: 14
 * 
 * @param values - Array of price values (typically closing prices)
 * @param period - Number of periods for RSI calculation (typically 14)
 * @returns Array with RSI values (0-100); null for positions before period is complete
 * 
 * @example
 * computeRSI([44, 44.5, 44.3, 45, 46], 3) → [null, null, null, ~60, ~75]
 */
export function computeRSI(values: number[], period: number) {
  const result: (number | null)[] = new Array(values.length).fill(null)
  let avgGain = 0
  let avgLoss = 0
  
  for (let i = 1; i < values.length; i += 1) {
    const change = values[i] - values[i - 1]
    const gain = Math.max(change, 0) // Positive changes are gains
    const loss = Math.max(-change, 0) // Negative changes are losses (made positive)
    
    if (i <= period) {
      // Initial period: accumulate gains and losses
      avgGain += gain
      avgLoss += loss
      if (i === period) {
        // At end of initial period, calculate simple averages
        avgGain /= period
        avgLoss /= period
      }
    } else {
      // After initial period: use smoothed moving average
      // This gives more weight to recent data (similar to EMA)
      avgGain = (avgGain * (period - 1) + gain) / period
      avgLoss = (avgLoss * (period - 1) + loss) / period
    }
    
    if (i >= period) {
      // Calculate RSI using the RS (Relative Strength) ratio
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss
      result[i] = 100 - 100 / (1 + rs) // Transform RS into 0-100 scale
    }
  }
  return result
}

/**
 * Computes MACD (Moving Average Convergence Divergence) - a trend-following momentum indicator.
 * 
 * MACD shows the relationship between two exponential moving averages and consists of:
 * 1. MACD Line: Fast EMA - Slow EMA (shows convergence/divergence of EMAs)
 * 2. Signal Line: EMA of MACD Line (smoothed MACD for identifying trends)
 * 3. Histogram: MACD Line - Signal Line (shows momentum strength)
 * 
 * Calculation:
 * - MACD Line = EMA(fast) - EMA(slow)
 * - Signal Line = EMA(MACD, signal period)
 * - Histogram = MACD Line - Signal Line
 * 
 * Typical parameters: fast=12, slow=26, signal=9
 * 
 * Interpretation:
 * - MACD crosses above signal: Bullish signal
 * - MACD crosses below signal: Bearish signal
 * - Histogram expanding: Trend strengthening
 * - Histogram contracting: Trend weakening
 * 
 * @param values - Array of price values (typically closing prices)
 * @param fast - Period for fast EMA (typically 12)
 * @param slow - Period for slow EMA (typically 26)
 * @param signal - Period for signal line EMA (typically 9)
 * @returns Object with {macd, signal, histogram} arrays
 * 
 * @example
 * computeMACD(prices, 12, 26, 9) → {macd: [...], signal: [...], histogram: [...]}
 */
export function computeMACD(values: number[], fast: number, slow: number, signal: number) {
  const fastEma = computeEMA(values, fast)
  const slowEma = computeEMA(values, slow)
  
  // MACD line is the difference between fast and slow EMAs
  const macd: (number | null)[] = new Array(values.length).fill(null)
  for (let i = 0; i < values.length; i += 1) {
    if (fastEma[i] !== null && slowEma[i] !== null) {
      macd[i] = (fastEma[i] as number) - (slowEma[i] as number)
    }
  }
  
  // Signal line is an EMA of the MACD line
  const macdValues = macd.map((v) => v ?? 0) // Convert nulls to 0 for EMA calculation
  const signalLine = computeEMA(macdValues, signal)
  
  // Histogram shows the difference between MACD and signal line
  const histogram: (number | null)[] = macd.map((v, i) =>
    v !== null && signalLine[i] !== null ? v - (signalLine[i] as number) : null
  )
  
  return { macd, signal: signalLine, histogram }
}

/**
 * Maps parallel time and value arrays into chart-compatible data points.
 * 
 * Converts separate arrays of timestamps and indicator values into the format
 * expected by lightweight-charts library: array of {time, value} objects.
 * Filters out null values to avoid gaps in the chart display.
 * 
 * @param times - Array of timestamp strings (e.g., '2024-01-15')
 * @param values - Array of indicator values (with possible nulls for incomplete periods)
 * @returns Array of {time, value} objects, excluding positions where value is null
 * 
 * @example
 * mapSeries(['2024-01-01', '2024-01-02', '2024-01-03'], [null, null, 42.5])
 * → [{time: '2024-01-03', value: 42.5}]
 */
export function mapSeries(times: string[], values: (number | null)[]) {
  return times
    .map((time, i) => (values[i] === null ? null : { time, value: values[i] as number }))
    .filter(Boolean) as { time: string; value: number }[]
}
