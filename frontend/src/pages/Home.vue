<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAssets } from '../composables/useAssets'
import { usePortfolioStore } from '../stores/portfolio'

const router = useRouter()
const { assets, errors, usage, fetchAssets, fetchAsset } = useAssets()
const portfolio = usePortfolioStore()

const lastRefresh = computed(() => {
  const times = assets.value.map((a) => a.fetched_at || 0)
  const max = Math.max(0, ...times)
  return max ? new Date(max * 1000).toLocaleString() : '--'
})

const dataStatus = computed(() => {
  const hasIssues = assets.value.some((a) => a.is_stale || a.missing || a.stooq_error) || errors.value.length
  return hasIssues ? 'Partial' : 'Fresh'
})

const favorites = computed(() => assets.value)

const exceptions = computed(() =>
  assets.value.filter((a) => a.missing || a.is_stale || a.stooq_error)
)

const priceBySymbol = computed(() =>
  assets.value.reduce((acc, a) => {
    acc[a.symbol] = a.latest_price
    return acc
  }, {})
)

const totalValue = computed(() =>
  portfolio.positions.reduce((sum, p) => sum + p.marketValue, 0)
)

const totalUnrealized = computed(() =>
  portfolio.positions.reduce((sum, p) => sum + p.unrealizedPnL, 0)
)

function formatPercent(value) {
  if (typeof value !== 'number') return '--'
  return `${(value * 100).toFixed(2)}%`
}

function formatMoney(value) {
  if (typeof value !== 'number') return '--'
  return value.toFixed(2)
}

function strengthFor(asset) {
  const score = Number(asset.score) || 0
  return Math.min(100, Math.round(Math.abs(score) * 25))
}

function formatFreshness(asset) {
  if (asset.missing) return 'Missing'
  return asset.is_stale ? 'Stale' : 'Fresh'
}

function goAnalyze(symbol) {
  router.push({ name: 'analyze', params: { symbol } })
}

async function refreshDaily() {
  await fetchAssets({ chartPoints: 60, interval: '1d', outputsize: 'compact', mode: 'daily' })
}

async function forceRefresh() {
  await fetchAssets({ chartPoints: 60, interval: '1d', outputsize: 'compact', mode: 'force' })
}

function recomputeLocal() {
  portfolio.recomputePositions(priceBySymbol.value)
}

async function loadPricesForEquity() {
  const symbols = Array.from(new Set(portfolio.transactions.map((tx) => tx.symbol.toUpperCase())))
  const map = {}
  await Promise.all(
    symbols.map(async (symbol) => {
      const asset = await fetchAsset({
        symbol,
        type: 'stock',
        interval: '1d',
        chartPoints: 260,
        outputsize: 'compact',
        refresh: false,
      })
      if (!asset) return
      map[symbol] = asset.dates.map((date, idx) => ({
        date,
        close: asset.series[idx],
      }))
    })
  )
  portfolio.recomputeEquityCurve(map)
}

onMounted(async () => {
  await fetchAssets({ chartPoints: 60, interval: '1d', outputsize: 'compact' })
  await portfolio.loadTransactions()
  portfolio.recomputePositions(priceBySymbol.value)
  await loadPricesForEquity()
})
</script>

<template>
  <div class="wrap home-page">
    <section class="home-topbar panel">
      <div class="status-row">
        <div class="status-chips">
          <div class="summary-pill muted">
            Data <strong>{{ dataStatus }}</strong>
            <small>Last refresh {{ lastRefresh }}</small>
          </div>
          <div class="summary-pill muted">
            Alpha <strong>{{ usage?.alpha.usedToday || 0 }} / {{ usage?.alpha.budget || 0 }}</strong>
            <small>{{ usage?.alpha.usedLastMinute || 0 }} calls last minute</small>
          </div>
        </div>
        <div class="status-actions">
          <button class="btn secondary" @click="refreshDaily">Refresh Daily</button>
          <button class="btn" @click="forceRefresh">Force</button>
          <button class="btn ghost" @click="recomputeLocal">Recompute</button>
        </div>
      </div>
    </section>

    <section class="home-main">
      <div class="panel">
        <h2>Favorites Snapshot</h2>
        <table class="favorites-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Signal</th>
              <th>Strength</th>
              <th>Return (30D)</th>
              <th>Vol (30D)</th>
              <th>Drawdown (3M)</th>
              <th class="is-muted">Provider</th>
              <th class="is-muted">Freshness</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="asset in favorites" :key="asset.symbol + asset.type" @click="goAnalyze(asset.symbol)">
              <td>{{ asset.symbol }}</td>
              <td><span class="pill" :class="asset.label">{{ asset.label }}</span></td>
              <td class="num">{{ strengthFor(asset) }}</td>
              <td class="num">{{ formatPercent(asset.features.ret_30d) }}</td>
              <td class="num">{{ formatPercent(asset.features.vol_30d) }}</td>
              <td class="num">{{ formatPercent(asset.features.drawdown_3m) }}</td>
              <td class="is-muted">{{ asset.provider || '--' }}</td>
              <td class="is-muted">{{ formatFreshness(asset) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel">
        <h2>Portfolio Summary</h2>
        <div class="summary-strip">
          <div>
            <span class="label">Total Value</span>
            <strong>{{ formatMoney(totalValue) }}</strong>
          </div>
          <div>
            <span class="label">Unrealized P/L</span>
            <strong>{{ formatMoney(totalUnrealized) }}</strong>
          </div>
          <div>
            <span class="label">Positions</span>
            <strong>{{ portfolio.positions.length }}</strong>
          </div>
          <div>
            <span class="label">Max Drawdown</span>
            <strong>{{ formatPercent(portfolio.maxDrawdown) }}</strong>
          </div>
        </div>

        <details class="exceptions">
          <summary>Alerts & Exceptions ({{ exceptions.length }})</summary>
          <ul>
            <li v-for="asset in exceptions" :key="asset.symbol + asset.type">
              <strong>{{ asset.symbol }}</strong> —
              <span v-if="asset.stooq_error === 'symbol_not_found'">Mapping needed</span>
              <span v-else-if="asset.missing">Missing data</span>
              <span v-else-if="asset.is_stale">Stale cache</span>
              <span v-else>Check provider</span>
            </li>
          </ul>
        </details>
      </div>
    </section>
  </div>
</template>
