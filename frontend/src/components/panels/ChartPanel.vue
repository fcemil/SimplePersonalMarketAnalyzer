<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { LineSeries } from 'lightweight-charts'
import { createChartCore } from '../../chart/chartCore'
import { computeSMA, computeEMA, computeBB, computeRSI, computeMACD, mapSeries } from '../../chart/indicators'
import { createDrawingLayer } from '../../chart/drawings'
import { loadIndicatorState, saveIndicatorState } from '../../chart/storage'
import { usePortfolioStore } from '../../stores/portfolio'

// Chart panel owns the TradingView-style chart and stat summary for the selected asset.
const props = defineProps({
  assets: { type: Array, required: true },
  selectedIndex: { type: Number, required: true },
  interval: { type: String, required: true },
  chartPoints: { type: Number, required: true },
  refreshSeconds: { type: Number, required: true },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'update:interval', 'update:chartPoints', 'refresh'])
const portfolio = usePortfolioStore()

const priceRef = ref(null)
const volumeRef = ref(null)
const rsiRef = ref(null)
const macdRef = ref(null)
const overlayRef = ref(null)
const chartWrapRef = ref(null)

const isFullscreen = ref(false)
const showIndicators = ref(false)
const showDrawings = ref(false)
const showSignals = ref(false)
const showBuys = ref(false)
const drawMode = ref('select')
const hoverState = ref({ time: null, o: null, h: null, l: null, c: null, changePct: null })

let core
let drawingLayer
let resizeObserver
const autoFitBySymbol = new Set()

const indicatorSeries = {
  sma20: null,
  sma50: null,
  sma200: null,
  ema12: null,
  ema26: null,
  bbUpper: null,
  bbMiddle: null,
  bbLower: null,
}

const indicatorState = ref({
  sma: { enabled: false, periods: [20, 50, 200] },
  ema: { enabled: false, periods: [12, 26] },
  bb: { enabled: false, period: 20, mult: 2 },
  rsi: { enabled: false, period: 14 },
  macd: { enabled: false, fast: 12, slow: 26, signal: 9 },
  volume: { enabled: false },
})

const selectedAsset = computed(() => props.assets[props.selectedIndex] || props.assets[0] || {
  features: { ret_30d: 0, vol_30d: 0, drawdown_3m: 0 },
  dates: [],
  series: [],
  ohlc: null,
})

const symbol = computed(() => selectedAsset.value?.symbol || 'UNKNOWN')

function formatPercent(value) {
  if (typeof value !== 'number') return '--'
  return `${(value * 100).toFixed(2)}%`
}

function onSelect(event) {
  emit('select', Number(event.target.value))
}

function updateInterval(event) {
  emit('update:interval', event.target.value)
}

function updateChartPoints(event) {
  emit('update:chartPoints', Number(event.target.value))
}

function requestRefresh() {
  emit('refresh')
}

function fitContent() {
  core?.priceChart?.timeScale().fitContent()
  autoFitBySymbol.add(symbol.value)
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
  document.body.style.overflow = isFullscreen.value ? 'hidden' : ''
  nextTick(() => resizeCharts())
}

function handleKeydown(evt) {
  if (evt.key === 'f') toggleFullscreen()
  if (evt.key === 'Escape' && isFullscreen.value) toggleFullscreen()
}

function updateHover(payload) {
  if (!payload?.bar) {
    hoverState.value = { time: null, o: null, h: null, l: null, c: null, changePct: null }
    return
  }
  const bar = payload.bar
  const o = bar.open ?? bar.value
  const h = bar.high ?? bar.value
  const l = bar.low ?? bar.value
  const c = bar.close ?? bar.value
  const changePct = o ? (c / o) - 1 : null
  hoverState.value = {
    time: payload.time,
    o,
    h,
    l,
    c,
    changePct,
  }
}

function applyIndicatorState() {
  saveIndicatorState(symbol.value, indicatorState.value)
  renderIndicators()
}

function renderIndicators() {
  if (!core) return
  const asset = selectedAsset.value
  const times = asset?.dates || []
  const closes = asset?.series || []

  if (indicatorState.value.sma.enabled) {
    indicatorSeries.sma20?.setData(mapSeries(times, computeSMA(closes, 20)))
    indicatorSeries.sma50?.setData(mapSeries(times, computeSMA(closes, 50)))
    indicatorSeries.sma200?.setData(mapSeries(times, computeSMA(closes, 200)))
  } else {
    indicatorSeries.sma20?.setData([])
    indicatorSeries.sma50?.setData([])
    indicatorSeries.sma200?.setData([])
  }

  if (indicatorState.value.ema.enabled) {
    indicatorSeries.ema12?.setData(mapSeries(times, computeEMA(closes, 12)))
    indicatorSeries.ema26?.setData(mapSeries(times, computeEMA(closes, 26)))
  } else {
    indicatorSeries.ema12?.setData([])
    indicatorSeries.ema26?.setData([])
  }

  if (indicatorState.value.bb.enabled) {
    const bands = computeBB(closes, indicatorState.value.bb.period, indicatorState.value.bb.mult)
    indicatorSeries.bbUpper?.setData(mapSeries(times, bands.upper))
    indicatorSeries.bbMiddle?.setData(mapSeries(times, bands.middle))
    indicatorSeries.bbLower?.setData(mapSeries(times, bands.lower))
  } else {
    indicatorSeries.bbUpper?.setData([])
    indicatorSeries.bbMiddle?.setData([])
    indicatorSeries.bbLower?.setData([])
  }

  if (indicatorState.value.rsi.enabled && core.rsiSeries) {
    const rsi = mapSeries(times, computeRSI(closes, indicatorState.value.rsi.period))
    core.rsiSeries.setData(rsi)
    core.rsiUpper?.setData(times.map((time) => ({ time, value: 70 })))
    core.rsiLower?.setData(times.map((time) => ({ time, value: 30 })))
  } else {
    core.rsiSeries?.setData([])
    core.rsiUpper?.setData([])
    core.rsiLower?.setData([])
  }

  if (indicatorState.value.macd.enabled && core.macdSeries) {
    const macd = computeMACD(closes, indicatorState.value.macd.fast, indicatorState.value.macd.slow, indicatorState.value.macd.signal)
    core.macdSeries.setData(mapSeries(times, macd.macd))
    core.macdSignal?.setData(mapSeries(times, macd.signal))
    core.macdHist?.setData(mapSeries(times, macd.histogram))
  } else {
    core.macdSeries?.setData([])
    core.macdSignal?.setData([])
    core.macdHist?.setData([])
  }

  if (indicatorState.value.volume.enabled && core.volumeSeries) {
    const volumeData = (asset?.ohlc || []).map((bar) => ({
      time: bar.time,
      value: bar.volume || 0,
      color: bar.close >= bar.open ? '#1f8a70' : '#b03a2e',
    }))
    core.volumeSeries.setData(volumeData)
  } else {
    core.volumeSeries?.setData([])
  }
}

function renderChart() {
  if (!core) return
  const asset = selectedAsset.value
  if (asset?.ohlc) {
    core.candleSeries.setData(asset.ohlc)
    core.lineSeries.setData([])
  } else {
    const lineData = asset?.dates?.map((d, i) => ({ time: d, value: asset.series[i] })) || []
    core.lineSeries.setData(lineData)
    core.candleSeries.setData([])
  }
  if (!autoFitBySymbol.has(symbol.value)) {
    core.priceChart.timeScale().fitContent()
    autoFitBySymbol.add(symbol.value)
  }
  renderIndicators()
  updateMarkers()
  drawingLayer?.redraw()
}

function updateMarkers() {
  if (!core) return
  const markers = []
  if (showSignals.value && Array.isArray(selectedAsset.value?.signal_markers)) {
    selectedAsset.value.signal_markers.forEach((m) => {
      markers.push({
        time: m.time,
        position: 'aboveBar',
        color: m.color || '#4a7c89',
        shape: 'circle',
        text: m.label || '',
      })
    })
  }
  if (showBuys.value) {
    portfolio.transactions
      .filter((tx) => tx.type === 'BUY' && tx.symbol === symbol.value)
      .forEach((tx) => {
        const time = tx.priceDateUsed || tx.dateEntered || tx.date
        markers.push({
          time,
          position: 'belowBar',
          color: '#1f8a70',
          shape: 'arrowUp',
          text: 'BUY',
        })
      })
  }
  if (selectedAsset.value?.ohlc && typeof core.candleSeries.setMarkers === 'function') {
    core.candleSeries.setMarkers(markers)
  }
}

function resizeCharts() {
  const resizeChart = (chart, refEl) => {
    if (!chart || !refEl) return
    const { clientWidth, clientHeight } = refEl
    if (clientWidth > 0 && clientHeight > 0) {
      chart.applyOptions({ width: clientWidth, height: clientHeight })
    }
  }
  resizeChart(core?.priceChart, priceRef.value)
  resizeChart(core?.volumeChart, volumeRef.value)
  resizeChart(core?.rsiChart, rsiRef.value)
  resizeChart(core?.macdChart, macdRef.value)
  drawingLayer?.resize()
}

watch(() => props.selectedIndex, () => {
  const stored = loadIndicatorState(symbol.value)
  if (stored) indicatorState.value = stored
  renderChart()
  drawingLayer?.setSymbol(symbol.value)
})

watch(
  () => props.assets[props.selectedIndex],
  () => renderChart(),
  { deep: true }
)

watch(indicatorState, () => applyIndicatorState(), { deep: true })

watch(
  () => [indicatorState.value.volume.enabled, indicatorState.value.rsi.enabled, indicatorState.value.macd.enabled],
  () => nextTick(() => resizeCharts())
)

watch([showSignals, showBuys, () => portfolio.transactions], () => updateMarkers(), { deep: true })

watch(drawMode, () => {
  drawingLayer?.setMode(drawMode.value)
})

watch(showDrawings, (next) => {
  if (next) {
    drawingLayer?.enable()
  } else {
    drawingLayer?.disable()
  }
})

onMounted(() => {
  core = createChartCore({
    priceRef: priceRef.value,
    volumeRef: volumeRef.value,
    rsiRef: rsiRef.value,
    macdRef: macdRef.value,
    onHover: updateHover,
  })

  indicatorSeries.sma20 = core.priceChart.addSeries(LineSeries, { color: '#4a7c89', lineWidth: 1 })
  indicatorSeries.sma50 = core.priceChart.addSeries(LineSeries, { color: '#8a9bb0', lineWidth: 1 })
  indicatorSeries.sma200 = core.priceChart.addSeries(LineSeries, { color: '#b69f8b', lineWidth: 1 })
  indicatorSeries.ema12 = core.priceChart.addSeries(LineSeries, { color: '#7b5ea7', lineWidth: 1 })
  indicatorSeries.ema26 = core.priceChart.addSeries(LineSeries, { color: '#a05c5c', lineWidth: 1 })
  indicatorSeries.bbUpper = core.priceChart.addSeries(LineSeries, { color: '#e0d6c8', lineWidth: 1 })
  indicatorSeries.bbMiddle = core.priceChart.addSeries(LineSeries, { color: '#d6c1a8', lineWidth: 1 })
  indicatorSeries.bbLower = core.priceChart.addSeries(LineSeries, { color: '#e0d6c8', lineWidth: 1 })

  drawingLayer = createDrawingLayer({
    canvas: overlayRef.value,
    chart: core.priceChart,
    series: core.candleSeries,
    symbol: symbol.value,
  })
  drawingLayer.disable()

  resizeObserver = new ResizeObserver(() => resizeCharts())
  ;[priceRef.value, volumeRef.value, rsiRef.value, macdRef.value, chartWrapRef.value].forEach((el) => {
    if (el) resizeObserver.observe(el)
  })
  resizeCharts()
  const stored = loadIndicatorState(symbol.value)
  if (stored) indicatorState.value = stored
  renderChart()

  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
  window.removeEventListener('keydown', handleKeydown)
  if (isFullscreen.value) document.body.style.overflow = ''
  drawingLayer?.destroy?.()
})
</script>

<template>
  <div class="panel" :class="{ fullscreen: isFullscreen }">
    <div class="panel-heading">
      <h2>Chart</h2>
      <div class="asset-select">
        <label for="asset-select">Asset</label>
        <select id="asset-select" :value="selectedIndex" @change="onSelect">
          <option v-for="(asset, idx) in assets" :key="asset.symbol + idx" :value="idx">
            {{ asset.name }} ({{ asset.type }})
          </option>
        </select>
      </div>
    </div>
    <div class="asset-meta">
      <span>Provider: {{ selectedAsset.provider || '—' }}</span>
      <span v-if="selectedAsset.fetched_at">Last fetched: {{ new Date(selectedAsset.fetched_at * 1000).toLocaleString() }}</span>
      <span v-if="selectedAsset.missing">Status: Missing</span>
      <span v-else-if="selectedAsset.is_stale">Status: Stale</span>
      <span v-else>Status: Fresh</span>
    </div>
    <div class="chart-controls">
      <div>
        <label>Interval</label>
        <select :value="interval" @change="updateInterval">
          <option value="1d">1D</option>
          <option value="1w">1W</option>
          <option value="1m">1M</option>
        </select>
      </div>
      <div>
        <label>History</label>
        <select :value="chartPoints" @change="updateChartPoints">
          <option :value="60">~3M</option>
          <option :value="100">~5M</option>
          <option :value="260">~1Y</option>
          <option :value="520">~2Y</option>
          <option :value="780">~3Y</option>
          <option :value="1040">~4Y</option>
          <option :value="1260">~5Y</option>
          <option v-if="interval === '1w'" :value="260">~5Y</option>
          <option v-if="interval === '1w'" :value="520">~10Y</option>
          <option v-if="interval === '1m'" :value="240">~20Y</option>
        </select>
      </div>
      <div class="refresh-cell">
        <label>Refresh</label>
        <button class="btn secondary" @click="requestRefresh">Refresh now</button>
      </div>
    </div>
    <div class="chart-actions">
      <button class="btn ghost mini" @click="fitContent">Fit</button>
      <button class="btn ghost mini" @click="showIndicators = !showIndicators">Indicators</button>
      <button class="btn ghost mini" @click="showDrawings = !showDrawings">Drawings</button>
      <button class="btn ghost mini" @click="showSignals = !showSignals">Signals</button>
      <button class="btn ghost mini" @click="showBuys = !showBuys">Buys</button>
      <button class="btn ghost mini" @click="toggleFullscreen">{{ isFullscreen ? 'Exit' : 'Fullscreen' }}</button>
      <span class="mode-chip" v-if="showDrawings">DRAW: {{ drawMode }}</span>
    </div>

    <div v-if="showIndicators" class="indicator-panel">
      <label><input type="checkbox" v-model="indicatorState.sma.enabled" /> SMA (20/50/200)</label>
      <label><input type="checkbox" v-model="indicatorState.ema.enabled" /> EMA (12/26)</label>
      <label><input type="checkbox" v-model="indicatorState.bb.enabled" /> Bollinger (20,2)</label>
      <label><input type="checkbox" v-model="indicatorState.volume.enabled" /> Volume</label>
      <label><input type="checkbox" v-model="indicatorState.rsi.enabled" /> RSI (14)</label>
      <label><input type="checkbox" v-model="indicatorState.macd.enabled" /> MACD (12,26,9)</label>
    </div>

    <div v-if="showDrawings" class="drawing-toolbar">
      <button class="btn ghost mini" @click="drawMode = 'select'">Select</button>
      <button class="btn ghost mini" @click="drawMode = 'trendline'">Trendline</button>
      <button class="btn ghost mini" @click="drawMode = 'hline'">HLine</button>
      <button class="btn ghost mini" @click="drawMode = 'rect'">Rectangle</button>
      <button class="btn ghost mini" @click="drawingLayer?.deleteSelected()">Delete</button>
    </div>

    <div class="chart-wrap" ref="chartWrapRef">
      <div class="chart-stack">
        <div class="chart-panel">
          <div ref="priceRef" class="chart-canvas"></div>
          <canvas ref="overlayRef" class="overlay-canvas" :class="{ active: showDrawings }"></canvas>
          <div v-if="hoverState.time" class="hover-tooltip">
            <div><strong>{{ hoverState.time }}</strong></div>
            <div>O: {{ hoverState.o?.toFixed?.(2) }}</div>
            <div>H: {{ hoverState.h?.toFixed?.(2) }}</div>
            <div>L: {{ hoverState.l?.toFixed?.(2) }}</div>
            <div>C: {{ hoverState.c?.toFixed?.(2) }}</div>
          </div>
        </div>
        <div ref="volumeRef" class="chart-sub" :class="{ hidden: !indicatorState.volume.enabled }"></div>
        <div ref="rsiRef" class="chart-sub" :class="{ hidden: !indicatorState.rsi.enabled }"></div>
        <div ref="macdRef" class="chart-sub" :class="{ hidden: !indicatorState.macd.enabled }"></div>
      </div>
      <div v-if="loading" class="chart-loading">
        <div class="spinner"></div>
        <span>Loading chart data...</span>
      </div>
    </div>
    <div class="chart-footer">
      <div class="stat">
        <strong>{{ formatPercent(selectedAsset.features.ret_30d) }}</strong>
        Return (30D)
      </div>
      <div class="stat">
        <strong>{{ formatPercent(selectedAsset.features.vol_30d) }}</strong>
        Vol (30D)
      </div>
      <div class="stat">
        <strong>{{ formatPercent(selectedAsset.features.drawdown_3m) }}</strong>
        Drawdown (3M)
      </div>
    </div>
  </div>
</template>
