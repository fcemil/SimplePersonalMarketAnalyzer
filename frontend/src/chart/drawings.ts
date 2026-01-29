import { saveDrawings, loadDrawings } from './storage'

type Point = { t: any; price: number }
type Drawing = {
  id: string
  type: 'trendline' | 'hline' | 'rect'
  p1: Point
  p2?: Point
}

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
  let mode: 'select' | 'trendline' | 'hline' | 'rect' = 'select'
  let currentSymbol = symbol
  let drawings: Drawing[] = (loadDrawings(currentSymbol) as Drawing[]) || []
  let selectedId: string | null = null
  let tempPoint: Point | null = null
  let enabled = false

  const ctx = canvas.getContext('2d')!

  const resize = () => {
    const rect = canvas.parentElement!.getBoundingClientRect()
    canvas.width = rect.width * devicePixelRatio
    canvas.height = rect.height * devicePixelRatio
    canvas.style.width = `${rect.width}px`
    canvas.style.height = `${rect.height}px`
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.scale(devicePixelRatio, devicePixelRatio)
    redraw()
  }

  const toPoint = (x: number, y: number) => {
    const time = chart.timeScale().coordinateToTime(x)
    const price = series.coordinateToPrice(y)
    if (time === null || price === null) return null
    return { t: time, price }
  }

  const toCoord = (p: Point) => {
    const x = chart.timeScale().timeToCoordinate(p.t)
    const y = series.priceToCoordinate(p.price)
    if (x === null || y === null) return null
    return { x, y }
  }

  const hitTest = (x: number, y: number) => {
    let hit: Drawing | null = null
    drawings.forEach((d) => {
      const c1 = toCoord(d.p1)
      const c2 = d.p2 ? toCoord(d.p2) : null
      if (!c1) return
      if (d.type === 'hline') {
        if (Math.abs(y - c1.y) < 6) hit = d
      } else if (d.type === 'trendline' && c2) {
        const dist = pointLineDistance({ x, y }, c1, c2)
        if (dist < 6) hit = d
      } else if (d.type === 'rect' && c2) {
        const minX = Math.min(c1.x, c2.x)
        const maxX = Math.max(c1.x, c2.x)
        const minY = Math.min(c1.y, c2.y)
        const maxY = Math.max(c1.y, c2.y)
        if (x >= minX && x <= maxX && y >= minY && y <= maxY) hit = d
      }
    })
    return hit
  }

  const redraw = () => {
    const rect = canvas.getBoundingClientRect()
    ctx.clearRect(0, 0, rect.width, rect.height)
    drawings.forEach((d) => drawShape(d, d.id === selectedId))
    if (tempPoint) {
      drawShape({ id: 'tmp', type: mode as any, p1: tempPoint, p2: tempPoint })
    }
  }

  const drawShape = (d: Drawing, selected = false) => {
    const c1 = toCoord(d.p1)
    const c2 = d.p2 ? toCoord(d.p2) : null
    if (!c1) return
    ctx.save()
    ctx.strokeStyle = selected ? '#4a7c89' : '#667085'
    ctx.lineWidth = selected ? 2 : 1
    if (d.type === 'hline') {
      ctx.beginPath()
      ctx.moveTo(0, c1.y)
      ctx.lineTo(canvas.getBoundingClientRect().width, c1.y)
      ctx.stroke()
    } else if (d.type === 'trendline' && c2) {
      ctx.beginPath()
      ctx.moveTo(c1.x, c1.y)
      ctx.lineTo(c2.x, c2.y)
      ctx.stroke()
    } else if (d.type === 'rect' && c2) {
      const w = c2.x - c1.x
      const h = c2.y - c1.y
      ctx.strokeRect(c1.x, c1.y, w, h)
    }
    ctx.restore()
  }

  const onClick = (evt: MouseEvent) => {
    const rect = canvas.getBoundingClientRect()
    const x = evt.clientX - rect.left
    const y = evt.clientY - rect.top
    if (mode === 'select') {
      const hit = hitTest(x, y)
      selectedId = hit ? hit.id : null
      redraw()
      return
    }
    if (mode === 'hline') {
      const p = toPoint(x, y)
      if (!p) return
      drawings.push({ id: crypto.randomUUID(), type: 'hline', p1: p })
      saveDrawings(currentSymbol, drawings)
      redraw()
      return
    }
    if (!tempPoint) {
      const p = toPoint(x, y)
      if (!p) return
      tempPoint = p
      return
    }
    const p2 = toPoint(x, y)
    if (!p2) return
    drawings.push({ id: crypto.randomUUID(), type: mode as any, p1: tempPoint, p2 })
    tempPoint = null
    saveDrawings(currentSymbol, drawings)
    redraw()
  }

  const onMove = (evt: MouseEvent) => {
    if (!tempPoint || mode === 'select') return
    const rect = canvas.getBoundingClientRect()
    const x = evt.clientX - rect.left
    const y = evt.clientY - rect.top
    const p2 = toPoint(x, y)
    if (!p2) return
    const temp = { id: 'preview', type: mode as any, p1: tempPoint, p2 }
    ctx.clearRect(0, 0, rect.width, rect.height)
    drawings.forEach((d) => drawShape(d, d.id === selectedId))
    drawShape(temp)
  }

  const onKeyDown = (evt: KeyboardEvent) => {
    if (evt.key === 'Delete' && selectedId) {
      drawings = drawings.filter((d) => d.id !== selectedId)
      selectedId = null
      saveDrawings(currentSymbol, drawings)
      redraw()
    }
  }

  const enable = () => {
    if (enabled) return
    enabled = true
    canvas.addEventListener('click', onClick)
    canvas.addEventListener('mousemove', onMove)
    window.addEventListener('keydown', onKeyDown)
  }

  const disable = () => {
    if (!enabled) return
    enabled = false
    canvas.removeEventListener('click', onClick)
    canvas.removeEventListener('mousemove', onMove)
    window.removeEventListener('keydown', onKeyDown)
  }

  const setMode = (next: typeof mode) => {
    mode = next
    tempPoint = null
    redraw()
  }

  const setSymbol = (nextSymbol: string) => {
    currentSymbol = nextSymbol
    drawings = (loadDrawings(currentSymbol) as Drawing[]) || []
    selectedId = null
    redraw()
  }

  const deleteSelected = () => {
    if (!selectedId) return
    drawings = drawings.filter((d) => d.id !== selectedId)
    selectedId = null
    saveDrawings(currentSymbol, drawings)
    redraw()
  }

  resize()
  chart.timeScale().subscribeVisibleLogicalRangeChange(redraw)

  return {
    resize,
    redraw,
    enable,
    disable,
    setMode,
    setSymbol,
    deleteSelected,
    destroy() {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(redraw)
      disable()
    },
  }
}

function pointLineDistance(p: { x: number; y: number }, a: { x: number; y: number }, b: { x: number; y: number }) {
  const A = p.x - a.x
  const B = p.y - a.y
  const C = b.x - a.x
  const D = b.y - a.y
  const dot = A * C + B * D
  const lenSq = C * C + D * D
  const param = lenSq !== 0 ? dot / lenSq : -1
  let xx
  let yy
  if (param < 0) {
    xx = a.x
    yy = a.y
  } else if (param > 1) {
    xx = b.x
    yy = b.y
  } else {
    xx = a.x + param * C
    yy = a.y + param * D
  }
  const dx = p.x - xx
  const dy = p.y - yy
  return Math.sqrt(dx * dx + dy * dy)
}
