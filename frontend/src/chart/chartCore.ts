import { CandlestickSeries, HistogramSeries, LineSeries, createChart } from 'lightweight-charts'

export function createChartCore({
  priceRef,
  volumeRef,
  rsiRef,
  macdRef,
  onHover,
}: {
  priceRef: HTMLElement
  volumeRef: HTMLElement | null
  rsiRef: HTMLElement | null
  macdRef: HTMLElement | null
  onHover?: (payload: any) => void
}) {
  const priceChart = createChart(priceRef, {
    layout: { background: { color: '#ffffff' }, textColor: '#0f1c2e' },
    grid: { vertLines: { color: '#edf0f4' }, horzLines: { color: '#edf0f4' } },
    timeScale: { timeVisible: true, secondsVisible: false },
    rightPriceScale: { borderColor: '#e3e6eb' },
    crosshair: { mode: 1 },
  })
  const volumeChart = volumeRef
    ? createChart(volumeRef, {
        layout: { background: { color: '#ffffff' }, textColor: '#0f1c2e' },
        grid: { vertLines: { color: '#edf0f4' }, horzLines: { color: '#edf0f4' } },
        timeScale: { timeVisible: true, secondsVisible: false },
        rightPriceScale: { borderColor: '#e3e6eb' },
      })
    : null
  const rsiChart = rsiRef
    ? createChart(rsiRef, {
        layout: { background: { color: '#ffffff' }, textColor: '#0f1c2e' },
        grid: { vertLines: { color: '#edf0f4' }, horzLines: { color: '#edf0f4' } },
        timeScale: { timeVisible: true, secondsVisible: false },
        rightPriceScale: { borderColor: '#e3e6eb' },
      })
    : null
  const macdChart = macdRef
    ? createChart(macdRef, {
        layout: { background: { color: '#ffffff' }, textColor: '#0f1c2e' },
        grid: { vertLines: { color: '#edf0f4' }, horzLines: { color: '#edf0f4' } },
        timeScale: { timeVisible: true, secondsVisible: false },
        rightPriceScale: { borderColor: '#e3e6eb' },
      })
    : null

  const candleSeries = priceChart.addSeries(CandlestickSeries, {
    upColor: '#1f8a70',
    downColor: '#b03a2e',
    borderDownColor: '#b03a2e',
    borderUpColor: '#1f8a70',
    wickDownColor: '#b03a2e',
    wickUpColor: '#1f8a70',
  })
  const lineSeries = priceChart.addSeries(LineSeries, { color: '#cb6d51', lineWidth: 2 })
  const volumeSeries = volumeChart?.addSeries(HistogramSeries, {
    color: '#9aa4b2',
    priceFormat: { type: 'volume' },
  })

  const rsiSeries = rsiChart?.addSeries(LineSeries, { color: '#4a7c89', lineWidth: 2 })
  const rsiUpper = rsiChart?.addSeries(LineSeries, { color: '#e0d6c8', lineWidth: 1 })
  const rsiLower = rsiChart?.addSeries(LineSeries, { color: '#e0d6c8', lineWidth: 1 })

  const macdSeries = macdChart?.addSeries(LineSeries, { color: '#4a7c89', lineWidth: 2 })
  const macdSignal = macdChart?.addSeries(LineSeries, { color: '#b03a2e', lineWidth: 1 })
  const macdHist = macdChart?.addSeries(HistogramSeries, { color: '#cbd5e1' })

  priceChart.subscribeCrosshairMove((param) => {
    if (!onHover) return
    const bar = param.seriesData.get(candleSeries) || param.seriesData.get(lineSeries)
    onHover({ time: param.time, bar })
  })

  const syncTimeRange = (range: any) => {
    if (!range || range.from == null || range.to == null) return
    volumeChart?.timeScale().setVisibleLogicalRange(range)
    rsiChart?.timeScale().setVisibleLogicalRange(range)
    macdChart?.timeScale().setVisibleLogicalRange(range)
  }
  priceChart.timeScale().subscribeVisibleLogicalRangeChange(syncTimeRange)

  return {
    priceChart,
    volumeChart,
    rsiChart,
    macdChart,
    candleSeries,
    lineSeries,
    volumeSeries,
    rsiSeries,
    rsiUpper,
    rsiLower,
    macdSeries,
    macdSignal,
    macdHist,
  }
}
