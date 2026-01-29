<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { LineSeries, createChart } from 'lightweight-charts'

const props = defineProps({
  equitySeries: { type: Array, default: () => [] },
  drawdownSeries: { type: Array, default: () => [] },
})

const chartRef = ref(null)
let chart
let equityLine
let drawdownLine
let resizeObserver

function renderChart() {
  if (!chart) return
  equityLine?.setData(props.equitySeries)
  drawdownLine?.setData(props.drawdownSeries)
  chart.timeScale().fitContent()
}

onMounted(() => {
  chart = createChart(chartRef.value, {
    layout: { background: { color: '#ffffff' }, textColor: '#0f1c2e' },
    grid: { vertLines: { color: '#edf0f4' }, horzLines: { color: '#edf0f4' } },
    rightPriceScale: { borderColor: '#e3e6eb' },
    timeScale: { timeVisible: true, secondsVisible: false },
  })
  equityLine = chart.addSeries(LineSeries, {
    color: '#4a7c89',
    lineWidth: 2,
  })
  drawdownLine = chart.addSeries(LineSeries, {
    color: '#b03a2e',
    lineWidth: 1,
    priceScaleId: 'drawdown',
  })
  chart.priceScale('drawdown').applyOptions({
    scaleMargins: { top: 0.8, bottom: 0.1 },
  })
  const resize = () => {
    if (!chartRef.value) return
    chart.applyOptions({
      width: chartRef.value.clientWidth,
      height: chartRef.value.clientHeight,
    })
    chart.timeScale().fitContent()
  }
  resizeObserver = new ResizeObserver(resize)
  resizeObserver.observe(chartRef.value)
  resize()
  renderChart()
})

watch(
  () => [props.equitySeries, props.drawdownSeries],
  () => renderChart(),
  { deep: true }
)

onBeforeUnmount(() => {
  if (resizeObserver && chartRef.value) resizeObserver.unobserve(chartRef.value)
})
</script>

<template>
  <div class="equity-chart">
    <div ref="chartRef" class="equity-chart-canvas"></div>
  </div>
</template>
