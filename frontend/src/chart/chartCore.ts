/**
 * Chart Core Module
 * 
 * Provides core chart initialization and setup functionality for the MarketAnalyzer.
 * Creates and configures multiple synchronized chart panels:
 * - Main price chart (candlestick or line)
 * - Volume histogram
 * - RSI (Relative Strength Index) oscillator
 * - MACD (Moving Average Convergence Divergence) indicator
 * 
 * All charts share a synchronized time axis for coordinated navigation.
 */

import { CandlestickSeries, HistogramSeries, LineSeries, createChart } from 'lightweight-charts'

/**
 * Creates and configures the complete chart system with all panels and series.
 * 
 * This is the main entry point for chart initialization. It creates up to 4 synchronized
 * chart panels and configures their visual appearance, series, and interaction handlers.
 * 
 * @param params - Configuration object
 * @param params.priceRef - DOM element to mount the main price chart (required)
 * @param params.volumeRef - DOM element for volume chart (null to disable)
 * @param params.rsiRef - DOM element for RSI chart (null to disable)
 * @param params.macdRef - DOM element for MACD chart (null to disable)
 * @param params.onHover - Optional callback triggered on crosshair movement with {time, bar} data
 * 
 * @returns Object containing all chart instances and series references for data binding
 */
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
  // Create the main price chart with white background and grid styling
  const priceChart = createChart(priceRef, {
    layout: { background: { color: '#ffffff' }, textColor: '#0f1c2e' },
    grid: { vertLines: { color: '#edf0f4' }, horzLines: { color: '#edf0f4' } },
    timeScale: { timeVisible: true, secondsVisible: false },
    rightPriceScale: { borderColor: '#e3e6eb' },
    crosshair: { mode: 1 }, // Mode 1: normal crosshair (tracks price and time)
  })
  
  // Create volume chart if container element provided
  const volumeChart = volumeRef
    ? createChart(volumeRef, {
        layout: { background: { color: '#ffffff' }, textColor: '#0f1c2e' },
        grid: { vertLines: { color: '#edf0f4' }, horzLines: { color: '#edf0f4' } },
        timeScale: { timeVisible: true, secondsVisible: false },
        rightPriceScale: { borderColor: '#e3e6eb' },
      })
    : null
  
  // Create RSI chart if container element provided
  const rsiChart = rsiRef
    ? createChart(rsiRef, {
        layout: { background: { color: '#ffffff' }, textColor: '#0f1c2e' },
        grid: { vertLines: { color: '#edf0f4' }, horzLines: { color: '#edf0f4' } },
        timeScale: { timeVisible: true, secondsVisible: false },
        rightPriceScale: { borderColor: '#e3e6eb' },
      })
    : null
  
  // Create MACD chart if container element provided
  const macdChart = macdRef
    ? createChart(macdRef, {
        layout: { background: { color: '#ffffff' }, textColor: '#0f1c2e' },
        grid: { vertLines: { color: '#edf0f4' }, horzLines: { color: '#edf0f4' } },
        timeScale: { timeVisible: true, secondsVisible: false },
        rightPriceScale: { borderColor: '#e3e6eb' },
      })
    : null

  // Add candlestick series to price chart (green for up bars, red for down bars)
  const candleSeries = priceChart.addSeries(CandlestickSeries, {
    upColor: '#1f8a70',
    downColor: '#b03a2e',
    borderDownColor: '#b03a2e',
    borderUpColor: '#1f8a70',
    wickDownColor: '#b03a2e',
    wickUpColor: '#1f8a70',
  })
  
  // Add line series to price chart (for line chart mode or overlays)
  const lineSeries = priceChart.addSeries(LineSeries, { color: '#cb6d51', lineWidth: 2 })
  
  // Add volume histogram series (gray bars)
  const volumeSeries = volumeChart?.addSeries(HistogramSeries, {
    color: '#9aa4b2',
    priceFormat: { type: 'volume' },
  })

  // Add RSI series with overbought (70) and oversold (30) reference lines
  const rsiSeries = rsiChart?.addSeries(LineSeries, { color: '#4a7c89', lineWidth: 2 })
  const rsiUpper = rsiChart?.addSeries(LineSeries, { color: '#e0d6c8', lineWidth: 1 }) // 70 level
  const rsiLower = rsiChart?.addSeries(LineSeries, { color: '#e0d6c8', lineWidth: 1 }) // 30 level

  // Add MACD series: main line, signal line, and histogram
  const macdSeries = macdChart?.addSeries(LineSeries, { color: '#4a7c89', lineWidth: 2 })
  const macdSignal = macdChart?.addSeries(LineSeries, { color: '#b03a2e', lineWidth: 1 })
  const macdHist = macdChart?.addSeries(HistogramSeries, { color: '#cbd5e1' })

  // Set up crosshair hover callback to extract bar data at cursor position
  priceChart.subscribeCrosshairMove((param) => {
    if (!onHover) return
    // Extract data from whichever series has data (candle or line)
    const bar = param.seriesData.get(candleSeries) || param.seriesData.get(lineSeries)
    onHover({ time: param.time, bar })
  })

  /**
   * Synchronizes the visible time range across all chart panels.
   * When the user zooms/pans the main chart, all indicator charts follow.
   * 
   * @param range - Logical range object with {from, to} properties
   */
  const syncTimeRange = (range: any) => {
    if (!range || range.from == null || range.to == null) return
    volumeChart?.timeScale().setVisibleLogicalRange(range)
    rsiChart?.timeScale().setVisibleLogicalRange(range)
    macdChart?.timeScale().setVisibleLogicalRange(range)
  }
  
  // Subscribe to price chart range changes to keep all panels synchronized
  priceChart.timeScale().subscribeVisibleLogicalRangeChange(syncTimeRange)

  // Return all chart and series references for external data binding
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
