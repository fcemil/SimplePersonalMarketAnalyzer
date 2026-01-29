/**
 * Chart Markers Module
 * 
 * Provides functionality to create visual markers on price charts for highlighting
 * significant events or trading signals. Markers appear as shapes (circles, arrows, etc.)
 * positioned above or below price bars.
 * 
 * Common use cases:
 * - Buy/sell signals from trading algorithms
 * - Important events (earnings, dividends, splits)
 * - Custom annotations
 */

/**
 * Converts an array of signal point objects into chart marker format.
 * 
 * Transforms custom signal data into the marker format expected by lightweight-charts.
 * Each marker is rendered as a visual indicator on the chart at a specific time point.
 * 
 * @param signalPoints - Array of signal objects with time, color, and text properties
 * @param signalPoints[].time - Timestamp for the marker (e.g., '2024-01-15')
 * @param signalPoints[].color - Optional marker color (defaults to '#4a7c89')
 * @param signalPoints[].text - Optional label text to display
 * 
 * @returns Array of marker objects compatible with lightweight-charts API
 * 
 * @example
 * buildSignalMarkers([
 *   { time: '2024-01-15', color: '#00ff00', text: 'BUY' },
 *   { time: '2024-01-20', color: '#ff0000', text: 'SELL' }
 * ])
 * // → markers rendered as circles above bars with labels
 */
export function buildSignalMarkers(signalPoints = []) {
  return signalPoints.map((point) => ({
    time: point.time,
    position: 'aboveBar', // Position marker above the price bar
    color: point.color || '#4a7c89', // Default teal color if not specified
    shape: 'circle', // Render as circular marker
    text: point.text || '', // Optional label text
  }))
}
