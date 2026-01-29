const INDICATOR_KEY = 'pm-indicators'
const DRAWING_KEY = 'pm-drawings'

function loadMap(key: string) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : {}
  } catch (err) {
    return {}
  }
}

function saveMap(key: string, value: Record<string, unknown>) {
  localStorage.setItem(key, JSON.stringify(value))
}

export function loadIndicatorState(symbol: string) {
  const map = loadMap(INDICATOR_KEY) as Record<string, unknown>
  return map[symbol] || null
}

export function saveIndicatorState(symbol: string, state: unknown) {
  const map = loadMap(INDICATOR_KEY) as Record<string, unknown>
  map[symbol] = state
  saveMap(INDICATOR_KEY, map)
}

export function loadDrawings(symbol: string) {
  const map = loadMap(DRAWING_KEY) as Record<string, unknown>
  return map[symbol] || []
}

export function saveDrawings(symbol: string, drawings: unknown) {
  const map = loadMap(DRAWING_KEY) as Record<string, unknown>
  map[symbol] = drawings
  saveMap(DRAWING_KEY, map)
}
