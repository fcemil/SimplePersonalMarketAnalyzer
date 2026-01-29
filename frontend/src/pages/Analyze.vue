<script setup>
import { computed, ref, watch } from 'vue'
import ChartPanel from '../components/panels/ChartPanel.vue'
import SignalsPanel from '../components/panels/SignalsPanel.vue'
import StatsCards from '../components/layout/StatsCards.vue'
import WarningBanner from '../components/layout/WarningBanner.vue'
import QuotaWidget from '../components/layout/QuotaWidget.vue'
import AssetDrawer from '../components/layout/AssetDrawer.vue'
import { useAssets } from '../composables/useAssets'
import { symbolMap } from '../config/symbolMap'

// Central analyze state lives here so chart + signals stay in sync.
const { assets, usingMock, errors, usage, fetchAssets, fetchAsset } = useAssets()
const selectedIndex = ref(0)
const isExpanded = ref(false)
const chartPanelRef = ref(null)
const chartLoading = ref(false)
const detailsOpen = ref(false)

const interval = ref('1d')
const chartPoints = ref(60)
const refreshSeconds = ref(0)
const stooqMapKey = 'stooqSymbolMap'
const stooqMap = ref(loadStooqMap())

function loadStooqMap() {
  let stored = {}
  try {
    stored = JSON.parse(localStorage.getItem(stooqMapKey) || '{}')
  } catch (err) {
    stored = {}
  }
  return { ...(symbolMap?.stooq || {}), ...stored }
}

function saveStooqMap(next) {
  stooqMap.value = next
  localStorage.setItem(stooqMapKey, JSON.stringify(next))
}

const counts = computed(() =>
  assets.value.reduce((acc, a) => {
    acc[a.label] = (acc[a.label] || 0) + 1
    return acc
  }, {})
)

async function loadAssets() {
  chartLoading.value = true
  try {
    await fetchAssets({
      interval: interval.value,
      chartPoints: chartPoints.value,
      outputsize: 'compact',
      stooqMap: stooqMap.value,
      mode: 'daily',
    })
  } finally {
    chartLoading.value = false
  }
}

async function refreshSelected() {
  const asset = assets.value[selectedIndex.value]
  if (!asset) return
  chartLoading.value = true
  try {
    await fetchAsset({
      symbol: asset.symbol,
      type: asset.type,
      interval: interval.value,
      chartPoints: chartPoints.value,
      outputsize: 'compact',
      refresh: true,
      mode: 'force',
      stooqSymbol: stooqMap.value[asset.symbol],
    })
  } finally {
    chartLoading.value = false
  }
}

async function updateSelected() {
  const asset = assets.value[selectedIndex.value]
  if (!asset) return
  chartLoading.value = true
  try {
    await fetchAsset({
      symbol: asset.symbol,
      type: asset.type,
      interval: interval.value,
      chartPoints: chartPoints.value,
      outputsize: 'compact',
      refresh: false,
      mode: 'daily',
      stooqSymbol: stooqMap.value[asset.symbol],
    })
  } finally {
    chartLoading.value = false
  }
}

async function addSymbol(symbol) {
  await fetch('/api/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol }),
  })
  location.reload()
}

async function removeSymbol(symbol) {
  await fetch(`/api/watchlist/${symbol}`, { method: 'DELETE' })
  location.reload()
}

function selectAsset(index) {
  selectedIndex.value = index
  detailsOpen.value = true
}

function toggleSignals() {
  isExpanded.value = !isExpanded.value
  setTimeout(() => chartPanelRef.value?.fitContent?.(), 150)
}

function setStooqSymbol(symbol, stooqSymbol) {
  const next = { ...stooqMap.value, [symbol]: stooqSymbol.trim().toLowerCase() }
  saveStooqMap(next)
  loadAssets()
}

watch([interval, chartPoints], () => updateSelected())

watch(interval, () => {
  if (interval.value === '1w' && chartPoints.value < 260) chartPoints.value = 260
  if (interval.value === '1m' && chartPoints.value < 240) chartPoints.value = 240
})

loadAssets()
</script>

<template>
  <div class="wrap">
    <WarningBanner v-if="usingMock" mode="mock" />
    <WarningBanner v-else-if="errors.length" mode="errors" :errors="errors" />

    <div class="analyze-grid" :class="{ open: detailsOpen }">
      <section class="row" :class="{ expanded: isExpanded }">
        <ChartPanel
          ref="chartPanelRef"
          :assets="assets"
          :selected-index="selectedIndex"
          :interval="interval"
          :chart-points="chartPoints"
          :refresh-seconds="refreshSeconds"
          :loading="chartLoading"
          @select="selectAsset"
          @update:interval="interval = $event"
          @update:chartPoints="chartPoints = $event"
          @refresh="refreshSelected"
        />

        <SignalsPanel
          :assets="assets"
          :selected-index="selectedIndex"
          :is-expanded="isExpanded"
          :stooq-map="stooqMap"
          @select="selectAsset"
          @add="addSymbol"
          @remove="removeSymbol"
          @toggle="toggleSignals"
          @set-stooq-symbol="setStooqSymbol"
        />
      </section>

      <AssetDrawer
        v-if="detailsOpen"
        :asset="assets[selectedIndex] || null"
        :open="detailsOpen"
        @close="detailsOpen = false"
        @set-stooq-symbol="setStooqSymbol"
      />
    </div>

    <StatsCards :total="assets.length" :counts="counts" />
    <QuotaWidget v-if="usage" :usage="usage" />
  </div>
</template>
