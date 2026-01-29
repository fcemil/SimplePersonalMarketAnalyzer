/**
 * Chart State Persistence Module
 * 
 * Provides localStorage-based persistence for chart configuration and user drawings.
 * Data is stored per symbol so each chart maintains its own state independently.
 * 
 * Two types of data are persisted:
 * 1. Indicator states: which indicators are visible and their parameters
 * 2. Drawings: user-drawn trendlines, support/resistance levels, annotations
 * 
 * Storage keys:
 * - 'pm-indicators': map of symbol → indicator configuration
 * - 'pm-drawings': map of symbol → array of drawing objects
 */

/** Storage key for indicator states */
const INDICATOR_KEY = 'pm-indicators'
/** Storage key for drawing states */
const DRAWING_KEY = 'pm-drawings'

/**
 * Safely loads and parses a JSON map from localStorage.
 * 
 * @param key - localStorage key to read from
 * @returns Parsed object map, or empty object if key doesn't exist or parse fails
 */
function loadMap(key: string) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : {}
  } catch (err) {
    // Return empty object if parsing fails (corrupted data)
    return {}
  }
}

/**
 * Serializes and saves an object map to localStorage.
 * 
 * @param key - localStorage key to write to
 * @param value - Object to serialize and store
 */
function saveMap(key: string, value: Record<string, unknown>) {
  localStorage.setItem(key, JSON.stringify(value))
}

/**
 * Loads saved indicator configuration for a specific symbol.
 * 
 * Returns the indicator state (which indicators are enabled, their parameters, etc.)
 * that was previously saved for this symbol.
 * 
 * @param symbol - Trading symbol (e.g., 'AAPL', 'TSLA')
 * @returns Saved indicator state object, or null if no state exists
 */
export function loadIndicatorState(symbol: string) {
  const map = loadMap(INDICATOR_KEY) as Record<string, unknown>
  return map[symbol] || null
}

/**
 * Saves indicator configuration for a specific symbol.
 * 
 * Persists which indicators are currently enabled and their parameters
 * so they can be restored when the chart is reloaded.
 * 
 * @param symbol - Trading symbol (e.g., 'AAPL', 'TSLA')
 * @param state - Indicator configuration object to save
 */
export function saveIndicatorState(symbol: string, state: unknown) {
  const map = loadMap(INDICATOR_KEY) as Record<string, unknown>
  map[symbol] = state
  saveMap(INDICATOR_KEY, map)
}

/**
 * Loads saved drawings for a specific symbol.
 * 
 * Returns the array of user-drawn shapes (trendlines, support/resistance levels, etc.)
 * that were previously saved for this symbol.
 * 
 * @param symbol - Trading symbol (e.g., 'AAPL', 'TSLA')
 * @returns Array of drawing objects, or empty array if no drawings exist
 */
export function loadDrawings(symbol: string) {
  const map = loadMap(DRAWING_KEY) as Record<string, unknown>
  return map[symbol] || []
}

/**
 * Saves drawings for a specific symbol.
 * 
 * Persists all user-drawn shapes so they appear when the chart is reloaded.
 * Each drawing includes its type, coordinates, and styling information.
 * 
 * @param symbol - Trading symbol (e.g., 'AAPL', 'TSLA')
 * @param drawings - Array of drawing objects to save
 */
export function saveDrawings(symbol: string, drawings: unknown) {
  const map = loadMap(DRAWING_KEY) as Record<string, unknown>
  map[symbol] = drawings
  saveMap(DRAWING_KEY, map)
}
