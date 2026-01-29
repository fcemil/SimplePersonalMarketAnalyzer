/**
 * Chart Drawing Tools Module
 * 
 * Provides interactive drawing capabilities on price charts for technical analysis.
 * Supports multiple drawing types:
 * - Trendlines: diagonal lines between two price points
 * - Horizontal lines: price levels
 * - Rectangles: price ranges over time periods
 * 
 * Features:
 * - Click-to-draw interface with multiple tool modes
 * - Selection and deletion of existing drawings
 * - Persistent storage per symbol
 * - Coordinate conversion between canvas pixels and chart time/price
 * - Hit testing for selection
 */

import { saveDrawings, loadDrawings } from './storage'

/** Represents a point in chart space (time and price) */
type Point = { t: any; price: number }

/** Represents a drawing shape on the chart */
type Drawing = {
  id: string // Unique identifier for selection/deletion
  type: 'trendline' | 'hline' | 'rect'
  p1: Point // First point (or only point for hline)
  p2?: Point // Second point (optional for hline)
}

/**
 * Creates an interactive drawing layer on top of a chart.
 * 
 * This function sets up a canvas overlay that allows users to draw technical analysis
 * shapes directly on the price chart. Drawings are stored per symbol and persisted to
 * localStorage.
 * 
 * @param params - Configuration object
 * @param params.canvas - HTML canvas element for drawing overlay
 * @param params.chart - Lightweight-charts chart instance for coordinate conversion
 * @param params.series - Chart series for price coordinate conversion
 * @param params.symbol - Current trading symbol (for persistent storage)
 * 
 * @returns Object with methods to control the drawing layer
 */
export function createDrawingLayer({
  canvas,
  chart,
  series,
  symbol,
}: {
  canvas: HTMLCanvasElement
  chart: any
  series: any
  symbol: string
}) {
  let mode: 'select' | 'trendline' | 'hline' | 'rect' = 'select' // Current drawing mode
  let currentSymbol = symbol
  let drawings: Drawing[] = (loadDrawings(currentSymbol) as Drawing[]) || []
  let selectedId: string | null = null // ID of currently selected drawing
  let tempPoint: Point | null = null // First point while drawing two-point shapes
  let enabled = false // Whether event listeners are active

  const ctx = canvas.getContext('2d')!

  /**
   * Resizes the canvas to match its container and account for device pixel ratio.
   * High DPI displays require scaling to avoid blurry rendering.
   */
  const resize = () => {
    const rect = canvas.parentElement!.getBoundingClientRect()
    // Scale canvas buffer size by device pixel ratio for crisp rendering
    canvas.width = rect.width * devicePixelRatio
    canvas.height = rect.height * devicePixelRatio
    // But keep CSS size at logical pixels
    canvas.style.width = `${rect.width}px`
    canvas.style.height = `${rect.height}px`
    // Reset transform and scale context to match pixel ratio
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.scale(devicePixelRatio, devicePixelRatio)
    redraw()
  }

  /**
   * Converts canvas pixel coordinates to chart space (time and price).
   * 
   * @param x - Horizontal pixel position on canvas
   * @param y - Vertical pixel position on canvas
   * @returns Point with chart time and price, or null if conversion fails
   */
  const toPoint = (x: number, y: number) => {
    const time = chart.timeScale().coordinateToTime(x)
    const price = series.coordinateToPrice(y)
    if (time === null || price === null) return null
    return { t: time, price }
  }

  /**
   * Converts chart space point (time and price) to canvas pixel coordinates.
   * 
   * @param p - Point with chart time and price
   * @returns Object with {x, y} pixel coordinates, or null if conversion fails
   */
  const toCoord = (p: Point) => {
    const x = chart.timeScale().timeToCoordinate(p.t)
    const y = series.priceToCoordinate(p.price)
    if (x === null || y === null) return null
    return { x, y }
  }

  /**
   * Tests if a mouse click hits any existing drawing (for selection).
   * Uses different hit test logic for each drawing type.
   * 
   * @param x - Mouse X position in canvas pixels
   * @param y - Mouse Y position in canvas pixels
   * @returns The hit drawing, or null if no drawing was clicked
   */
  const hitTest = (x: number, y: number) => {
    let hit: Drawing | null = null
    drawings.forEach((d) => {
      const c1 = toCoord(d.p1)
      const c2 = d.p2 ? toCoord(d.p2) : null
      if (!c1) return
      
      if (d.type === 'hline') {
        // Horizontal line: check if Y coordinate is within 6 pixels
        if (Math.abs(y - c1.y) < 6) hit = d
      } else if (d.type === 'trendline' && c2) {
        // Trendline: calculate perpendicular distance to line segment
        const dist = pointLineDistance({ x, y }, c1, c2)
        if (dist < 6) hit = d
      } else if (d.type === 'rect' && c2) {
        // Rectangle: check if point is inside bounds
        const minX = Math.min(c1.x, c2.x)
        const maxX = Math.max(c1.x, c2.x)
        const minY = Math.min(c1.y, c2.y)
        const maxY = Math.max(c1.y, c2.y)
        if (x >= minX && x <= maxX && y >= minY && y <= maxY) hit = d
      }
    })
    return hit
  }

  /**
   * Redraws all drawings on the canvas.
   * Clears the canvas and renders all stored drawings, highlighting the selected one.
   */
  const redraw = () => {
    const rect = canvas.getBoundingClientRect()
    ctx.clearRect(0, 0, rect.width, rect.height)
    // Draw all persisted drawings
    drawings.forEach((d) => drawShape(d, d.id === selectedId))
    // Draw temporary preview while drawing
    if (tempPoint) {
      drawShape({ id: 'tmp', type: mode as any, p1: tempPoint, p2: tempPoint })
    }
  }

  /**
   * Renders a single drawing shape on the canvas.
   * 
   * @param d - Drawing to render
   * @param selected - Whether this drawing is currently selected (affects color/width)
   */
  const drawShape = (d: Drawing, selected = false) => {
    const c1 = toCoord(d.p1)
    const c2 = d.p2 ? toCoord(d.p2) : null
    if (!c1) return
    
    ctx.save()
    // Selected drawings are highlighted with different color and thicker line
    ctx.strokeStyle = selected ? '#4a7c89' : '#667085'
    ctx.lineWidth = selected ? 2 : 1
    
    if (d.type === 'hline') {
      // Horizontal line spans entire canvas width
      ctx.beginPath()
      ctx.moveTo(0, c1.y)
      ctx.lineTo(canvas.getBoundingClientRect().width, c1.y)
      ctx.stroke()
    } else if (d.type === 'trendline' && c2) {
      // Trendline is a straight line between two points
      ctx.beginPath()
      ctx.moveTo(c1.x, c1.y)
      ctx.lineTo(c2.x, c2.y)
      ctx.stroke()
    } else if (d.type === 'rect' && c2) {
      // Rectangle defined by two corner points
      const w = c2.x - c1.x
      const h = c2.y - c1.y
      ctx.strokeRect(c1.x, c1.y, w, h)
    }
    ctx.restore()
  }

  /**
   * Handles mouse click events for drawing and selection.
   * Behavior varies by current mode:
   * - select: select/deselect drawings
   * - hline: add horizontal line at click Y coordinate
   * - trendline/rect: start drawing on first click, complete on second click
   */
  const onClick = (evt: MouseEvent) => {
    const rect = canvas.getBoundingClientRect()
    const x = evt.clientX - rect.left
    const y = evt.clientY - rect.top
    
    if (mode === 'select') {
      // In select mode, clicking selects/deselects drawings
      const hit = hitTest(x, y)
      selectedId = hit ? hit.id : null
      redraw()
      return
    }
    
    if (mode === 'hline') {
      // Horizontal lines only need one click
      const p = toPoint(x, y)
      if (!p) return
      drawings.push({ id: crypto.randomUUID(), type: 'hline', p1: p })
      saveDrawings(currentSymbol, drawings)
      redraw()
      return
    }
    
    // For trendline and rect, need two clicks
    if (!tempPoint) {
      // First click: store starting point
      const p = toPoint(x, y)
      if (!p) return
      tempPoint = p
      return
    }
    
    // Second click: complete the drawing
    const p2 = toPoint(x, y)
    if (!p2) return
    drawings.push({ id: crypto.randomUUID(), type: mode as any, p1: tempPoint, p2 })
    tempPoint = null
    saveDrawings(currentSymbol, drawings)
    redraw()
  }

  /**
   * Handles mouse move events to show preview while drawing two-point shapes.
   * 
   * @param evt - Mouse move event
   */
  const onMove = (evt: MouseEvent) => {
    if (!tempPoint || mode === 'select') return
    const rect = canvas.getBoundingClientRect()
    const x = evt.clientX - rect.left
    const y = evt.clientY - rect.top
    const p2 = toPoint(x, y)
    if (!p2) return
    // Show preview of shape being drawn
    const temp = { id: 'preview', type: mode as any, p1: tempPoint, p2 }
    ctx.clearRect(0, 0, rect.width, rect.height)
    drawings.forEach((d) => drawShape(d, d.id === selectedId))
    drawShape(temp)
  }

  /**
   * Handles keyboard events, primarily for deleting selected drawings.
   * 
   * @param evt - Keyboard event
   */
  const onKeyDown = (evt: KeyboardEvent) => {
    // Delete key removes the currently selected drawing
    if (evt.key === 'Delete' && selectedId) {
      drawings = drawings.filter((d) => d.id !== selectedId)
      selectedId = null
      saveDrawings(currentSymbol, drawings)
      redraw()
    }
  }

  /**
   * Enables drawing layer by attaching event listeners.
   * Prevents double-enabling to avoid duplicate listeners.
   */
  const enable = () => {
    if (enabled) return
    enabled = true
    canvas.addEventListener('click', onClick)
    canvas.addEventListener('mousemove', onMove)
    window.addEventListener('keydown', onKeyDown)
  }

  /**
   * Disables drawing layer by removing event listeners.
   * Prevents errors from removing non-existent listeners.
   */
  const disable = () => {
    if (!enabled) return
    enabled = false
    canvas.removeEventListener('click', onClick)
    canvas.removeEventListener('mousemove', onMove)
    window.removeEventListener('keydown', onKeyDown)
  }

  /**
   * Changes the current drawing mode.
   * Resets any in-progress drawing when mode changes.
   * 
   * @param next - New drawing mode to activate
   */
  const setMode = (next: typeof mode) => {
    mode = next
    tempPoint = null
    redraw()
  }

  /**
   * Switches to a different symbol, loading its saved drawings.
   * Clears selection and redraws canvas.
   * 
   * @param nextSymbol - Symbol to switch to (e.g., 'AAPL', 'TSLA')
   */
  const setSymbol = (nextSymbol: string) => {
    currentSymbol = nextSymbol
    drawings = (loadDrawings(currentSymbol) as Drawing[]) || []
    selectedId = null
    redraw()
  }

  /**
   * Deletes the currently selected drawing and saves changes.
   */
  const deleteSelected = () => {
    if (!selectedId) return
    drawings = drawings.filter((d) => d.id !== selectedId)
    selectedId = null
    saveDrawings(currentSymbol, drawings)
    redraw()
  }

  // Initialize: set canvas size and subscribe to chart range changes
  resize()
  chart.timeScale().subscribeVisibleLogicalRangeChange(redraw)

  // Return API for controlling the drawing layer
  return {
    resize,
    redraw,
    enable,
    disable,
    setMode,
    setSymbol,
    deleteSelected,
    destroy() {
      // Cleanup: unsubscribe from chart and remove event listeners
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(redraw)
      disable()
    },
  }
}

/**
 * Calculates the perpendicular distance from a point to a line segment.
 * 
 * Uses vector projection to find the closest point on the line segment to the test point,
 * then calculates the Euclidean distance. Handles cases where the closest point is beyond
 * the segment endpoints (returns distance to nearest endpoint).
 * 
 * This is used for hit testing trendlines - if the distance is within a threshold (6 pixels),
 * the user clicked on the line.
 * 
 * @param p - Test point {x, y}
 * @param a - First endpoint of line segment {x, y}
 * @param b - Second endpoint of line segment {x, y}
 * @returns Distance in pixels from point to line segment
 */
function pointLineDistance(p: { x: number; y: number }, a: { x: number; y: number }, b: { x: number; y: number }) {
  // Vector from a to p
  const A = p.x - a.x
  const B = p.y - a.y
  // Vector from a to b (line segment direction)
  const C = b.x - a.x
  const D = b.y - a.y
  
  // Project p onto line using dot product
  const dot = A * C + B * D
  const lenSq = C * C + D * D
  
  // Parameter t represents position along line: 0 = point a, 1 = point b
  const param = lenSq !== 0 ? dot / lenSq : -1
  
  let xx
  let yy
  if (param < 0) {
    // Closest point is before segment start, use point a
    xx = a.x
    yy = a.y
  } else if (param > 1) {
    // Closest point is after segment end, use point b
    xx = b.x
    yy = b.y
  } else {
    // Closest point is on the segment
    xx = a.x + param * C
    yy = a.y + param * D
  }
  
  // Return Euclidean distance from p to closest point
  const dx = p.x - xx
  const dy = p.y - yy
  return Math.sqrt(dx * dx + dy * dy)
}
