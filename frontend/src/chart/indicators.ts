export function computeSMA(values: number[], period: number) {
  const result: (number | null)[] = new Array(values.length).fill(null)
  let sum = 0
  for (let i = 0; i < values.length; i += 1) {
    sum += values[i]
    if (i >= period) sum -= values[i - period]
    if (i >= period - 1) result[i] = sum / period
  }
  return result
}

export function computeEMA(values: number[], period: number) {
  const result: (number | null)[] = new Array(values.length).fill(null)
  const k = 2 / (period + 1)
  let ema = values[0]
  for (let i = 0; i < values.length; i += 1) {
    ema = i === 0 ? values[0] : values[i] * k + ema * (1 - k)
    if (i >= period - 1) result[i] = ema
  }
  return result
}

export function computeBB(values: number[], period: number, mult: number) {
  const middle = computeSMA(values, period)
  const upper: (number | null)[] = new Array(values.length).fill(null)
  const lower: (number | null)[] = new Array(values.length).fill(null)
  for (let i = period - 1; i < values.length; i += 1) {
    const window = values.slice(i - period + 1, i + 1)
    const mean = middle[i] ?? 0
    const variance = window.reduce((acc, v) => acc + Math.pow(v - mean, 2), 0) / period
    const sd = Math.sqrt(variance)
    upper[i] = mean + mult * sd
    lower[i] = mean - mult * sd
  }
  return { middle, upper, lower }
}

export function computeRSI(values: number[], period: number) {
  const result: (number | null)[] = new Array(values.length).fill(null)
  let avgGain = 0
  let avgLoss = 0
  for (let i = 1; i < values.length; i += 1) {
    const change = values[i] - values[i - 1]
    const gain = Math.max(change, 0)
    const loss = Math.max(-change, 0)
    if (i <= period) {
      avgGain += gain
      avgLoss += loss
      if (i === period) {
        avgGain /= period
        avgLoss /= period
      }
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period
      avgLoss = (avgLoss * (period - 1) + loss) / period
    }
    if (i >= period) {
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss
      result[i] = 100 - 100 / (1 + rs)
    }
  }
  return result
}

export function computeMACD(values: number[], fast: number, slow: number, signal: number) {
  const fastEma = computeEMA(values, fast)
  const slowEma = computeEMA(values, slow)
  const macd: (number | null)[] = new Array(values.length).fill(null)
  for (let i = 0; i < values.length; i += 1) {
    if (fastEma[i] !== null && slowEma[i] !== null) {
      macd[i] = (fastEma[i] as number) - (slowEma[i] as number)
    }
  }
  const macdValues = macd.map((v) => v ?? 0)
  const signalLine = computeEMA(macdValues, signal)
  const histogram: (number | null)[] = macd.map((v, i) =>
    v !== null && signalLine[i] !== null ? v - (signalLine[i] as number) : null
  )
  return { macd, signal: signalLine, histogram }
}

export function mapSeries(times: string[], values: (number | null)[]) {
  return times
    .map((time, i) => (values[i] === null ? null : { time, value: values[i] as number }))
    .filter(Boolean) as { time: string; value: number }[]
}
