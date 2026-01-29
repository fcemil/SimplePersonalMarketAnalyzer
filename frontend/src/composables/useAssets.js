import { ref } from 'vue'

// Centralized asset fetching with a mock fallback.
export function useAssets() {
  const assets = ref([])
  const usingMock = ref(false)
  const errors = ref([])
  const usage = ref(null)

  const mockAssets = [
    {
      name: 'AAPL',
      symbol: 'AAPL',
      type: 'stock',
      label: 'bullish',
      score: 2,
      reasons: ['Positive 1-month return (over +3%).'],
      features: { ret_30d: 0.041, vol_30d: 0.21, drawdown_3m: -0.04, ma20_slope: 0.01 },
      latest_price: 185.1,
      change_pct: 0.009,
      provider: 'stooq',
      fetched_at: Date.now() / 1000,
      expires_at: Date.now() / 1000 + 3600,
      is_stale: false,
      analysis_window_days: 30,
      drawdown_window_days: 63,
      sample_count: 120,
      feature_contributions: [
        { feature: 'Return(30D)', value: 0.041, impact: 2 },
        { feature: 'MA20 Slope', value: 0.01, impact: 1 },
      ],
      dates: ['2026-01-02', '2026-01-03', '2026-01-04', '2026-01-05', '2026-01-06'],
      series: [180.2, 181.3, 179.9, 183.4, 185.1],
      ohlc: [
        { time: '2026-01-02', open: 179.2, high: 181.7, low: 178.8, close: 180.2 },
        { time: '2026-01-03', open: 180.2, high: 182.1, low: 179.6, close: 181.3 },
        { time: '2026-01-04', open: 181.3, high: 182.0, low: 179.3, close: 179.9 },
        { time: '2026-01-05', open: 179.9, high: 183.9, low: 179.7, close: 183.4 },
        { time: '2026-01-06', open: 183.4, high: 186.2, low: 182.8, close: 185.1 },
      ],
    },
    {
      name: 'WTI Crude',
      symbol: 'DCOILWTICO',
      type: 'commodity',
      label: 'neutral',
      score: 0,
      reasons: ['No strong signal'],
      features: { ret_30d: 0.012, vol_30d: 0.32, drawdown_3m: -0.07, ma20_slope: -0.01 },
      latest_price: 72.0,
      change_pct: 0.004,
      provider: 'fred',
      fetched_at: Date.now() / 1000,
      expires_at: Date.now() / 1000 + 3600,
      is_stale: false,
      analysis_window_days: 30,
      drawdown_window_days: 63,
      sample_count: 120,
      feature_contributions: [{ feature: 'Return(30D)', value: 0.012, impact: 0 }],
      dates: ['2026-01-02', '2026-01-03', '2026-01-04', '2026-01-05', '2026-01-06'],
      series: [71.2, 70.9, 72.3, 71.7, 72.0],
      ohlc: null,
    },
  ]

  async function fetchAssets({
    interval = '1d',
    chartPoints = 60,
    outputsize = 'compact',
    stooqMap = null,
    mode = 'daily',
  } = {}) {
    try {
      const url = new URL('/api/assets', window.location.origin)
      url.searchParams.set('interval', interval)
      url.searchParams.set('chart_points', String(chartPoints))
      url.searchParams.set('outputsize', outputsize)
      url.searchParams.set('mode', mode)
      if (stooqMap) url.searchParams.set('stooq_map', JSON.stringify(stooqMap))
      const res = await fetch(url)
      if (!res.ok) throw new Error('assets endpoint missing')
      const data = await res.json()
      const nextAssets = data.assets || []
      errors.value = data.errors || []
      usage.value = data.usage || null
      if (errors.value.length && assets.value.length) {
        const existingByKey = new Map(
          assets.value.map((a) => [`${a.type}:${a.symbol}`, a])
        )
        nextAssets.forEach((a) => existingByKey.set(`${a.type}:${a.symbol}`, a))
        assets.value = Array.from(existingByKey.values())
      } else {
        assets.value = nextAssets
      }
    } catch (err) {
      usingMock.value = true
      assets.value = mockAssets
    }
  }

  async function fetchAsset({
    symbol,
    type,
    interval = '1d',
    chartPoints = 60,
    outputsize = 'compact',
    refresh = false,
    mode = 'daily',
    stooqSymbol = null,
  }) {
    if (!symbol || !type) return null
    try {
      const url = new URL('/api/asset', window.location.origin)
      url.searchParams.set('symbol', symbol)
      url.searchParams.set('type', type)
      url.searchParams.set('interval', interval)
      url.searchParams.set('chart_points', String(chartPoints))
      url.searchParams.set('outputsize', outputsize)
      url.searchParams.set('mode', mode)
      if (stooqSymbol) url.searchParams.set('stooq_symbol', stooqSymbol)
      if (refresh) url.searchParams.set('refresh', '1')
      const res = await fetch(url)
      if (!res.ok) throw new Error('asset endpoint missing')
      const data = await res.json()
      const updated = data.asset
      if (!updated) return null
      const idx = assets.value.findIndex((a) => a.symbol === updated.symbol && a.type === updated.type)
      if (idx >= 0) {
        assets.value.splice(idx, 1, updated)
      } else {
        assets.value.push(updated)
      }
      return updated
    } catch (err) {
      return null
    }
  }

  return { assets, usingMock, errors, usage, fetchAssets, fetchAsset }
}
