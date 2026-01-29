<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import EquityChart from '../components/portfolio/EquityChart.vue'
import { useAssets } from '../composables/useAssets'
import { usePortfolioStore } from '../stores/portfolio'
import { useSettingsStore } from '../stores/settings'
import { computeFee } from '../utils/fees'
import { getCloseOnOrBefore } from '../services/prices'

const { assets, fetchAssets, fetchAsset } = useAssets()
const portfolio = usePortfolioStore()
const settings = useSettingsStore()

const form = ref({
  symbol: '',
  dateEntered: new Date().toISOString().slice(0, 10),
  gross: 0,
  currency: 'USD',
  notes: '',
})

const advancedOpen = ref(false)
const overrides = ref({
  price: '',
  fee: '',
  qty: '',
})

const preview = ref({
  priceDateUsed: null,
  price: null,
  provider: null,
  freshness: null,
  fee: null,
  qty: null,
  net: null,
  impliedGross: null,
  roundingDiff: null,
  error: null,
})

const editState = ref({
  id: null,
  gross: '',
  dateEntered: '',
})

const priceBySymbol = computed(() =>
  assets.value.reduce((acc, a) => {
    acc[a.symbol] = a.latest_price
    return acc
  }, {})
)

const equitySeries = computed(() =>
  portfolio.equityCurve.map((point) => ({ time: point.time, value: point.value }))
)
const drawdownSeries = computed(() =>
  portfolio.equityCurve.map((point) => ({ time: point.time, value: point.drawdown }))
)

const totalValue = computed(() =>
  portfolio.positions.reduce((sum, p) => sum + p.marketValue, 0)
)

const totalUnrealized = computed(() =>
  portfolio.positions.reduce((sum, p) => sum + p.unrealizedPnL, 0)
)

const totalUnrealizedPct = computed(() => (totalValue.value ? totalUnrealized.value / totalValue.value : 0))

function formatPercent(value) {
  if (typeof value !== 'number') return '--'
  return `${(value * 100).toFixed(2)}%`
}

function formatMoney(value) {
  if (typeof value !== 'number') return '--'
  return value.toFixed(2)
}

function roundTo(value, precision) {
  const factor = Math.pow(10, precision)
  return Math.round(value * factor) / factor
}

async function computePreview() {
  preview.value.error = null
  const symbol = form.value.symbol.trim().toUpperCase()
  const date = form.value.dateEntered
  const gross = Number(form.value.gross) || 0

  if (!symbol || !date || !gross) {
    preview.value = { ...preview.value, error: null }
    return
  }

  const asset = await fetchAsset({
    symbol,
    type: 'stock',
    interval: '1d',
    chartPoints: 520,
    outputsize: 'compact',
    refresh: false,
  })

  const priceInfo = asset ? getCloseOnOrBefore(asset, date) : { error: 'Missing price history' }
  if (priceInfo.error) {
    preview.value = { ...preview.value, error: priceInfo.error }
    return
  }

  const feePolicy = settings.feePolicy
  let fee = computeFee(gross, feePolicy)
  if (advancedOpen.value && overrides.value.fee !== '') {
    fee = Number(overrides.value.fee) || 0
  }
  if (fee >= gross) {
    preview.value = { ...preview.value, error: 'Amount too small after fees' }
    return
  }

  let price = priceInfo.close
  if (advancedOpen.value && overrides.value.price !== '') {
    price = Number(overrides.value.price) || price
  }

  const net = gross - fee
  let qty = net / price
  if (advancedOpen.value && overrides.value.qty !== '') {
    qty = Number(overrides.value.qty) || qty
  }
  const qtyRounded = roundTo(qty, settings.quantityPrecision)
  const impliedNet = qtyRounded * price
  const impliedGross = impliedNet + fee
  const roundingDiff = impliedGross - gross

  preview.value = {
    priceDateUsed: priceInfo.usedDate,
    price,
    provider: priceInfo.provider,
    freshness: priceInfo.freshness,
    fee,
    qty: qtyRounded,
    net,
    impliedGross,
    roundingDiff,
    error: null,
  }
}

async function submitBuy() {
  await computePreview()
  if (preview.value.error) return

  const symbol = form.value.symbol.trim().toUpperCase()
  const tx = {
    id: crypto.randomUUID(),
    type: 'BUY',
    symbol,
    dateEntered: form.value.dateEntered,
    priceDateUsed: preview.value.priceDateUsed,
    currency: form.value.currency,
    gross: Number(form.value.gross),
    fee: Number(preview.value.fee),
    price: Number(preview.value.price),
    qty: Number(preview.value.qty),
    provider: preview.value.provider,
    createdAt: new Date().toISOString(),
    notes: form.value.notes || '',
  }

  await portfolio.addBuySimple(tx)
  form.value = {
    symbol: '',
    dateEntered: new Date().toISOString().slice(0, 10),
    gross: 0,
    currency: 'USD',
    notes: '',
  }
  overrides.value = { price: '', fee: '', qty: '' }
  preview.value = { ...preview.value, error: null }
}

async function removeTx(id) {
  await portfolio.deleteTx(id)
}

function startEdit(tx) {
  editState.value = {
    id: tx.id,
    gross: tx.gross,
    dateEntered: tx.dateEntered || tx.date,
  }
}

function cancelEdit() {
  editState.value = { id: null, gross: '', dateEntered: '' }
}

async function saveEdit(tx) {
  const updated = { ...tx }
  updated.dateEntered = editState.value.dateEntered
  updated.gross = Number(editState.value.gross)

  const asset = await fetchAsset({
    symbol: tx.symbol,
    type: 'stock',
    interval: '1d',
    chartPoints: 520,
    outputsize: 'compact',
    refresh: false,
  })
  const priceInfo = asset ? getCloseOnOrBefore(asset, updated.dateEntered) : { error: 'Missing price history' }
  if (priceInfo.error) return

  const feePolicy = settings.feePolicy
  const fee = computeFee(updated.gross, feePolicy)
  if (fee >= updated.gross) return

  const net = updated.gross - fee
  const qty = roundTo(net / priceInfo.close, settings.quantityPrecision)

  updated.priceDateUsed = priceInfo.usedDate
  updated.fee = fee
  updated.price = priceInfo.close
  updated.qty = qty
  updated.provider = priceInfo.provider

  await portfolio.editBuySimple(updated)
  cancelEdit()
}

async function loadPriceSeries() {
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

async function refreshPortfolioSymbols() {
  const symbols = Array.from(new Set(portfolio.transactions.map((tx) => tx.symbol.toUpperCase())))
  await Promise.all(
    symbols.map((symbol) =>
      fetchAsset({
        symbol,
        type: 'stock',
        interval: '1d',
        chartPoints: 60,
        outputsize: 'compact',
        refresh: false,
      })
    )
  )
}

onMounted(async () => {
  await fetchAssets({ chartPoints: 60, interval: '1d', outputsize: 'compact' })
  await portfolio.loadTransactions()
  await refreshPortfolioSymbols()
  portfolio.recomputePositions(priceBySymbol.value)
  await loadPriceSeries()
  await computePreview()
})

watch([() => form.value.symbol, () => form.value.dateEntered, () => form.value.gross], () => {
  computePreview()
})

watch([() => advancedOpen.value, () => overrides.value.price, () => overrides.value.fee, () => overrides.value.qty], () => {
  computePreview()
})

watch(() => settings.feePolicy, () => {
  computePreview()
}, { deep: true })

watch(() => settings.quantityPrecision, () => {
  computePreview()
})

watch(priceBySymbol, (next) => {
  portfolio.recomputePositions(next)
})

watch(
  () => portfolio.transactions,
  async () => {
    await refreshPortfolioSymbols()
    await loadPriceSeries()
  },
  { deep: true }
)
</script>

<template>
  <div class="wrap portfolio-page">
    <section class="portfolio-strip">
      <div class="card compact">
        <h3>Total Value</h3>
        <div class="value">{{ formatMoney(totalValue) }}</div>
      </div>
      <div class="card compact">
        <h3>Unrealized P/L</h3>
        <div class="value">{{ formatMoney(totalUnrealized) }}</div>
        <small>{{ formatPercent(totalUnrealizedPct) }}</small>
      </div>
      <div class="card compact">
        <h3>Realized P/L</h3>
        <div class="value">{{ formatMoney(portfolio.realizedPnL) }}</div>
      </div>
      <div class="card compact">
        <h3>Positions</h3>
        <div class="value">{{ portfolio.positions.length }}</div>
      </div>
      <div class="card compact">
        <h3>Max Drawdown</h3>
        <div class="value">{{ formatPercent(portfolio.maxDrawdown) }}</div>
      </div>
    </section>

    <section class="panel">
      <h2>Equity Curve</h2>
      <EquityChart :equity-series="equitySeries" :drawdown-series="drawdownSeries" />
    </section>

    <section class="portfolio-grid">
      <div class="panel">
        <h2>Add Purchase</h2>
        <form class="tx-form simple" @submit.prevent="submitBuy">
          <label>
            Symbol
            <input v-model="form.symbol" placeholder="AAPL" required />
          </label>
          <label>
            Date
            <input type="date" v-model="form.dateEntered" required />
          </label>
          <label>
            Money spent
            <input type="number" step="0.01" v-model="form.gross" required />
          </label>
          <label>
            Currency
            <select v-model="form.currency">
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
            </select>
          </label>
          <label class="notes">
            Notes
            <input v-model="form.notes" placeholder="Optional notes" />
          </label>

          <div class="preview">
            <div>
              <span class="label">Price used</span>
              <strong>{{ preview.price ? formatMoney(preview.price) : '--' }}</strong>
              <small v-if="preview.priceDateUsed">{{ preview.priceDateUsed }}</small>
            </div>
            <div>
              <span class="label">Fees</span>
              <strong>{{ preview.fee !== null ? formatMoney(preview.fee) : '--' }}</strong>
            </div>
            <div>
              <span class="label">Quantity</span>
              <strong>{{ preview.qty !== null ? preview.qty : '--' }}</strong>
            </div>
            <div>
              <span class="label">Net invested</span>
              <strong>{{ preview.net !== null ? formatMoney(preview.net) : '--' }}</strong>
            </div>
          </div>
          <div v-if="preview.roundingDiff && Math.abs(preview.roundingDiff) > 0.01" class="rounding-note">
            Rounding difference: {{ formatMoney(preview.roundingDiff) }}
          </div>
          <div v-if="preview.error" class="form-error">{{ preview.error }}</div>

          <button class="btn" type="submit">Add purchase</button>
          <button class="btn ghost" type="button" @click="advancedOpen = !advancedOpen">
            {{ advancedOpen ? 'Hide advanced' : 'Advanced' }}
          </button>

          <div v-if="advancedOpen" class="advanced">
            <label>
              Override price
              <input type="number" step="0.0001" v-model="overrides.price" />
            </label>
            <label>
              Override fees
              <input type="number" step="0.01" v-model="overrides.fee" />
            </label>
            <label>
              Force quantity
              <input type="number" step="0.0001" v-model="overrides.qty" />
            </label>
          </div>
        </form>
      </div>

      <div class="panel">
        <h2>Positions</h2>
        <table class="portfolio-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Quantity</th>
              <th>Avg Cost</th>
              <th>Market</th>
              <th>Value</th>
              <th>Unrealized P/L</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pos in portfolio.positions" :key="pos.symbol">
              <td>{{ pos.symbol }}</td>
              <td>{{ pos.quantity.toFixed(settings.quantityPrecision) }}</td>
              <td>{{ formatMoney(pos.avgCost) }}</td>
              <td>{{ formatMoney(pos.marketPrice) }}</td>
              <td>{{ formatMoney(pos.marketValue) }}</td>
              <td>{{ formatMoney(pos.unrealizedPnL) }} ({{ formatPercent(pos.unrealizedPnLPct) }})</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>Transactions</h2>
      <table class="portfolio-table">
        <thead>
          <tr>
            <th>Date entered</th>
            <th>Price date</th>
            <th>Symbol</th>
            <th>Gross</th>
            <th>Fee</th>
            <th>Price</th>
            <th>Qty</th>
            <th>Provider</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tx in portfolio.transactions" :key="tx.id">
            <td v-if="editState.id !== tx.id">{{ tx.dateEntered || tx.date }}</td>
            <td v-else>
              <input type="date" v-model="editState.dateEntered" />
            </td>
            <td>{{ tx.priceDateUsed }}</td>
            <td>{{ tx.symbol }}</td>
            <td v-if="editState.id !== tx.id">{{ formatMoney(tx.gross) }}</td>
            <td v-else>
              <input type="number" step="0.01" v-model="editState.gross" />
            </td>
            <td>{{ formatMoney(tx.fee) }}</td>
            <td>{{ formatMoney(tx.price) }}</td>
            <td>{{ tx.qty }}</td>
            <td>{{ tx.provider }}</td>
            <td>
              <div class="tx-actions">
                <button v-if="editState.id !== tx.id" class="btn ghost mini" @click="startEdit(tx)">Edit</button>
                <button v-else class="btn secondary mini" @click="saveEdit(tx)">Save</button>
                <button v-if="editState.id === tx.id" class="btn ghost mini" @click="cancelEdit">Cancel</button>
                <button class="btn ghost mini" @click="removeTx(tx.id)">Delete</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>
