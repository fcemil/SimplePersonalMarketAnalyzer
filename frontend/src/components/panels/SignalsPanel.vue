<script setup>
import { computed, ref } from 'vue'

// Right-side signals panel with compact and expanded modes.
const props = defineProps({
  assets: { type: Array, required: true },
  selectedIndex: { type: Number, required: true },
  isExpanded: { type: Boolean, required: true },
  stooqMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['select', 'add', 'remove', 'toggle', 'set-stooq-symbol'])

const panelFilter = ref('')
const addSymbolValue = ref('')
const groupSortKey = ref('name')
const tableSortKey = ref('name')
const tableSortDir = ref('asc')
const stooqDrafts = ref({})
const signalFilter = ref('all')
const freshnessFilter = ref('all')
const providerFilter = ref('all')

const filteredAssets = computed(() => {
  const filter = panelFilter.value.trim().toLowerCase()
  return props.assets.filter((a) => {
    const matchesText = !filter || `${a.name} ${a.symbol} ${a.type}`.toLowerCase().includes(filter)
    const matchesSignal = signalFilter.value === 'all' || a.label === signalFilter.value
    const freshness = a.missing ? 'missing' : a.is_stale ? 'stale' : 'fresh'
    const matchesFresh = freshnessFilter.value === 'all' || freshness === freshnessFilter.value
    const matchesProvider = providerFilter.value === 'all' || (a.provider || 'unknown') === providerFilter.value
    return matchesText && matchesSignal && matchesFresh && matchesProvider
  })
})

const groupedAssets = computed(() => {
  const groups = {}
  const sortKey = groupSortKey.value
  filteredAssets.value.forEach((a) => {
    if (!groups[a.type]) groups[a.type] = []
    groups[a.type].push({ asset: a, idx: props.assets.indexOf(a) })
  })
  Object.keys(groups).forEach((key) => {
    groups[key].sort((x, y) => {
      const av = getSortValue(x.asset, sortKey)
      const bv = getSortValue(y.asset, sortKey)
      if (typeof av === 'number' && typeof bv === 'number') return av - bv
      return String(av).localeCompare(String(bv))
    })
  })
  return groups
})

const sortedTable = computed(() => {
  const items = [...filteredAssets.value]
  items.sort((a, b) => {
    const av = getSortValue(a, tableSortKey.value)
    const bv = getSortValue(b, tableSortKey.value)
    if (typeof av === 'number' && typeof bv === 'number') {
      return tableSortDir.value === 'asc' ? av - bv : bv - av
    }
    return tableSortDir.value === 'asc'
      ? String(av).localeCompare(String(bv))
      : String(bv).localeCompare(String(av))
  })
  return items
})

function getSortValue(asset, key) {
  if (key === 'name') return asset.name
  if (key === 'type') return asset.type
  if (key === 'label') return asset.label
  if (key === 'strength') return Math.abs(Number(asset.score) || 0)
  if (key === 'ret_30d') return asset.features.ret_30d
  if (key === 'vol_30d') return asset.features.vol_30d
  if (key === 'drawdown_3m') return asset.features.drawdown_3m
  if (key === 'sample_count') return asset.sample_count
  return ''
}

function formatPercent(value) {
  if (typeof value !== 'number') return '--'
  return `${(value * 100).toFixed(2)}%`
}

function formatPrice(value) {
  if (typeof value !== 'number') return '--'
  return value.toFixed(2)
}

function formatCurrency(asset) {
  return asset.currency ? asset.currency : 'USD'
}

function changeClass(asset) {
  if (typeof asset.change_pct !== 'number') return ''
  return asset.change_pct >= 0 ? 'price-up' : 'price-down'
}

function formatFreshness(asset) {
  if (asset.missing) return 'Missing'
  return asset.is_stale ? 'Stale' : 'Fresh'
}

function formatDate(value) {
  if (!value) return '--'
  return new Date(value * 1000).toLocaleDateString()
}

function getDraft(symbol) {
  return stooqDrafts.value[symbol] ?? props.stooqMap[symbol] ?? ''
}

function setDraft(symbol, value) {
  stooqDrafts.value = { ...stooqDrafts.value, [symbol]: value }
}

function submitStooq(symbol) {
  const value = (stooqDrafts.value[symbol] ?? '').trim()
  if (!value) return
  emit('set-stooq-symbol', symbol, value)
}

function submitAdd() {
  const symbol = addSymbolValue.value.trim()
  if (!symbol) return
  emit('add', symbol)
  addSymbolValue.value = ''
}

function setSort(key) {
  if (tableSortKey.value === key) {
    tableSortDir.value = tableSortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    tableSortKey.value = key
    tableSortDir.value = 'asc'
  }
}

function strengthFor(asset) {
  const score = Number(asset.score) || 0
  const strength = Math.min(100, Math.round(Math.abs(score) * 25))
  return { strength, signed: Math.round(score * 25) }
}

const summary = computed(() => {
  const counts = { bullish: 0, neutral: 0, bearish: 0, stale: 0, missing: 0 }
  props.assets.forEach((a) => {
    if (a.label && counts[a.label] !== undefined) counts[a.label] += 1
    if (a.missing) counts.missing += 1
    else if (a.is_stale) counts.stale += 1
  })
  return counts
})
</script>

<template>
  <div class="panel">
    <div class="panel-heading">
      <h2>Signals & Features</h2>
      <button class="btn icon secondary" @click="$emit('toggle')">{{ isExpanded ? 'Collapse' : 'Expand' }}</button>
    </div>
    <div class="signals-panel" :class="{ expanded: isExpanded }">
      <div class="signals-summary">
        <div class="summary-pill bullish">Bullish <strong>{{ summary.bullish }}</strong></div>
        <div class="summary-pill neutral">Neutral <strong>{{ summary.neutral }}</strong></div>
        <div class="summary-pill bearish">Bearish <strong>{{ summary.bearish }}</strong></div>
        <div class="summary-pill muted">Stale <strong>{{ summary.stale }}</strong></div>
        <div class="summary-pill muted">Missing <strong>{{ summary.missing }}</strong></div>
      </div>
      <div class="signals-toolbar">
        <input class="search-input" type="text" placeholder="Search assets..." v-model="panelFilter" />
        <div class="toolbar-row">
          <div class="toolbar-inline">
            <input class="search-input" type="text" placeholder="Add symbol (e.g. NFLX)" v-model="addSymbolValue" />
            <button class="btn" @click="submitAdd">Add</button>
          </div>
          <div class="toolbar-inline">
            <select v-model="groupSortKey">
              <option value="name">Sort: Name</option>
              <option value="label">Sort: Signal</option>
              <option value="ret_30d">Sort: Return (30D)</option>
            </select>
            <div class="toolbar-note">Grouped by type</div>
          </div>
        </div>
        <div class="signals-filters">
          <label>
            Signal
            <select v-model="signalFilter">
              <option value="all">All</option>
              <option value="bullish">Bullish</option>
              <option value="neutral">Neutral</option>
              <option value="bearish">Bearish</option>
            </select>
          </label>
          <label>
            Freshness
            <select v-model="freshnessFilter">
              <option value="all">All</option>
              <option value="fresh">Fresh</option>
              <option value="stale">Stale</option>
              <option value="missing">Missing</option>
            </select>
          </label>
          <label>
            Provider
            <select v-model="providerFilter">
              <option value="all">All</option>
              <option value="stooq">Stooq</option>
              <option value="alpha">Alpha</option>
              <option value="fred">FRED</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
        </div>
      </div>

      <div v-if="!isExpanded" class="signals-list">
        <div v-for="(groupAssets, group) in groupedAssets" :key="group" class="signals-group">
          <h3>{{ group }}</h3>
          <div
            v-for="item in groupAssets"
            :key="item.asset.symbol + item.idx"
            class="signals-row"
            :class="{ active: item.idx === selectedIndex }"
            @click="$emit('select', item.idx)"
          >
            <div class="name">{{ item.asset.name }}</div>
            <div class="signal-inline">
              <span class="pill" :class="item.asset.label">{{ item.asset.label }}</span>
              <span class="price" :class="changeClass(item.asset)">
                {{ formatPrice(item.asset.latest_price) }} {{ formatCurrency(item.asset) }}
                <small>{{ formatPercent(item.asset.change_pct) }}</small>
              </span>
            </div>
            <div class="return">{{ formatPercent(item.asset.features.ret_30d) }}</div>
            <div class="meta">
              <span class="meta-chip">{{ item.asset.provider || '—' }}</span>
              <span class="meta-chip">{{ formatFreshness(item.asset) }}</span>
              <span class="meta-chip">Strength {{ strengthFor(item.asset).strength }}</span>
            </div>
            <button
              v-if="item.asset.type === 'stock'"
              class="btn ghost mini row-remove"
              @click.stop="$emit('remove', item.asset.symbol)"
            >
              ✕
            </button>
            <div
              v-if="item.asset.stooq_error === 'symbol_not_found' && item.asset.type === 'stock'"
              class="mapping-inline"
              @click.stop
            >
              <input
                class="search-input"
                type="text"
                :value="getDraft(item.asset.symbol)"
                @input="setDraft(item.asset.symbol, $event.target.value)"
                placeholder="Set Stooq symbol"
              />
              <button class="btn secondary" @click="submitStooq(item.asset.symbol)">Save</button>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="signals-table-wrap">
        <table>
          <thead>
            <tr>
              <th><button @click="setSort('name')">Asset <span class="sort-indicator">↕</span></button></th>
              <th><button @click="setSort('type')">Type <span class="sort-indicator">↕</span></button></th>
              <th><button @click="setSort('label')">Signal <span class="sort-indicator">↕</span></button></th>
              <th><button @click="setSort('strength')">Strength <span class="sort-indicator">↕</span></button></th>
              <th><button @click="setSort('ret_30d')">Return (30D) <span class="sort-indicator">↕</span></button></th>
              <th><button @click="setSort('vol_30d')">Vol (30D) <span class="sort-indicator">↕</span></button></th>
              <th><button @click="setSort('drawdown_3m')">Drawdown (3M) <span class="sort-indicator">↕</span></button></th>
              <th>Provider</th>
              <th>Freshness</th>
              <th>Last Fetched</th>
              <th><button @click="setSort('sample_count')">Samples <span class="sort-indicator">↕</span></button></th>
              <th>Currency</th>
              <th>Reasons</th>
              <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="asset in sortedTable" :key="asset.symbol + asset.type">
                  <td>{{ asset.name }}</td>
                  <td>{{ asset.type }}</td>
                  <td><span class="pill" :class="asset.label">{{ asset.label }}</span></td>
                  <td>{{ strengthFor(asset).strength }}</td>
                  <td>{{ formatPercent(asset.features.ret_30d) }}</td>
                  <td>{{ formatPercent(asset.features.vol_30d) }}</td>
                  <td>{{ formatPercent(asset.features.drawdown_3m) }}</td>
                  <td>{{ asset.provider || '--' }}</td>
                  <td>{{ formatFreshness(asset) }}</td>
                  <td>{{ formatDate(asset.fetched_at) }}</td>
                  <td>{{ asset.sample_count || '--' }}</td>
                  <td>{{ formatCurrency(asset) }}</td>
                  <td class="reasons">{{ asset.reasons.length ? asset.reasons.join('; ') : 'No strong signal' }}</td>
                  <td>
                <div
                  v-if="asset.stooq_error === 'symbol_not_found' && asset.type === 'stock'"
                  class="mapping-inline"
                >
                  <input
                    class="search-input"
                    type="text"
                    :value="getDraft(asset.symbol)"
                    @input="setDraft(asset.symbol, $event.target.value)"
                    placeholder="Set Stooq symbol"
                  />
                  <button class="btn secondary" @click="submitStooq(asset.symbol)">Save</button>
                </div>
                <button v-if="asset.type === 'stock'" class="btn ghost" @click="$emit('remove', asset.symbol)">
                  Remove
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="disclaimer">
          This dashboard provides signal labels based on simple technical rules for the last ~30 trading days.
          It is for personal experimentation only and does not provide investment advice.
        </p>
      </div>
    </div>
  </div>
</template>
