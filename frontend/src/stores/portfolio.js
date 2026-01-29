/**
 * Portfolio Store - Manages transaction history and position calculations.
 * 
 * Features:
 * - Stores transactions in IndexedDB (persistent across sessions)
 * - Computes positions using Weighted Average Cost (WAC) method
 * - Calculates realized P&L from SELL transactions
 * - Generates equity curve from transaction history + price data
 * - Tracks maximum drawdown
 * 
 * Position Calculation (WAC method):
 * - BUY: Add to position, update average cost
 * - SELL: Realize profit/loss, reduce position
 * 
 * All monetary values are stored without fees factored into price.
 * Fees are tracked separately in transaction.fee field.
 */
import { defineStore } from 'pinia'
import { addTransaction, deleteTransaction, getAllTransactions, updateTransaction } from '../lib/idb'

/**
 * Sort transactions by date entered (or date if dateEntered missing).
 * Stable sort using id as tiebreaker.
 */
function sortByDate(a, b) {
  const aDate = a.dateEntered || a.date || ''
  const bDate = b.dateEntered || b.date || ''
  if (aDate === bDate) return String(a.id || '').localeCompare(String(b.id || ''))
  return String(aDate).localeCompare(String(bDate))
}

export const usePortfolioStore = defineStore('portfolio', {
  state: () => ({
    transactions: [],  // All transactions (BUY/SELL) sorted by date
    positions: [],  // Current positions with cost basis and P&L
    realizedPnL: 0,  // Total realized profit/loss from SELL transactions
    equityCurve: [],  // Daily portfolio value history
    maxDrawdown: 0,  // Maximum drawdown from peak equity
    lastLoadedAt: null,  // Timestamp of last data load
  }),
  actions: {
    /**
     * Load all transactions from IndexedDB.
     * Normalizes data and recomputes positions.
     */
    async loadTransactions() {
      const items = await getAllTransactions()
      const list = Array.isArray(items) ? items.filter(Boolean) : []
      // Ensure all transactions have an id
      const normalized = list.map((tx) => ({
        ...tx,
        id: tx?.id || crypto.randomUUID(),
      }))
      this.transactions = normalized.sort(sortByDate)
      this.recomputePositions()
      this.lastLoadedAt = Date.now()
    },
    /**
     * Add a new transaction and recompute positions.
     */
    async addTx(tx) {
      await addTransaction(tx)
      this.transactions = [...this.transactions, tx].sort(sortByDate)
      this.recomputePositions()
    },
    /**
     * Update an existing transaction and recompute positions.
     */
    async editTx(tx) {
      await updateTransaction(tx)
      const next = this.transactions.map((item) => (item.id === tx.id ? tx : item))
      this.transactions = next.sort(sortByDate)
      this.recomputePositions()
    },
    /**
     * Delete a transaction and recompute positions.
     */
    async deleteTx(id) {
      await deleteTransaction(id)
      this.transactions = this.transactions.filter((item) => item.id !== id)
      this.recomputePositions()
    },
    /**
     * Add a BUY transaction (simplified interface).
     */
    async addBuySimple(tx) {
      await addTransaction(tx)
      this.transactions = [...this.transactions, tx].sort(sortByDate)
      this.recomputePositions()
    },
    /**
     * Update a BUY transaction (simplified interface).
     */
    async editBuySimple(tx) {
      await updateTransaction(tx)
      const next = this.transactions.map((item) => (item.id === tx.id ? tx : item))
      this.transactions = next.sort(sortByDate)
      this.recomputePositions()
    },
    /**
     * Recompute all positions from transaction history using WAC method.
     * 
     * @param {Object} priceBySymbol - Optional current prices for unrealized P&L calc
     * 
     * WAC (Weighted Average Cost) method:
     * - BUY: Increase position size, update average cost
     * - SELL: Decrease position size, realize P&L based on average cost
     */
    recomputePositions(priceBySymbol = {}) {
      const positions = new Map()
      let realizedPnL = 0

      // Process transactions in chronological order
      this.transactions.forEach((tx) => {
        const symbol = tx.symbol
        if (!positions.has(symbol)) {
          positions.set(symbol, { symbol, quantity: 0, avgCost: 0, costBasis: 0 })
        }
        const pos = positions.get(symbol)
        const qty = Number(tx.qty ?? tx.quantity) || 0
        const gross = Number(tx.gross ?? (qty * (Number(tx.price) || 0) + (Number(tx.fee) || 0))) || 0
        const price = Number(tx.price) || 0
        const fee = Number(tx.fee ?? tx.fees) || 0

        if (tx.type === 'BUY') {
          // Add to position and update weighted average cost
          const newCostBasis = pos.costBasis + gross
          const newQty = pos.quantity + qty
          pos.quantity = newQty
          pos.costBasis = newCostBasis
          pos.avgCost = newQty ? newCostBasis / newQty : 0
        } else if (tx.type === 'SELL') {
          // Realize P&L and reduce position
          const sellQty = Math.min(pos.quantity, qty)
          realizedPnL += sellQty * (price - pos.avgCost) - fee
          const newQty = pos.quantity - sellQty
          pos.quantity = newQty
          pos.costBasis = pos.avgCost * newQty
        }
      })

      // Calculate unrealized P&L for each position using current market prices
      const mapped = Array.from(positions.values()).map((pos) => {
        const marketPrice = Number(priceBySymbol[pos.symbol]) || 0
        const marketValue = marketPrice * pos.quantity
        const unrealizedPnL = marketValue - pos.costBasis
        const unrealizedPnLPct = pos.costBasis ? unrealizedPnL / pos.costBasis : 0
        return {
          ...pos,
          marketPrice,
          marketValue,
          unrealizedPnL,
          unrealizedPnLPct,
        }
      })

      // Only show positions with non-zero quantity
      this.positions = mapped.filter((pos) => pos.quantity > 0)
      this.realizedPnL = realizedPnL
    },
    /**
     * Generate equity curve from transaction history and price data.
     * 
     * @param {Object} priceSeriesBySymbol - Price history for each symbol
     *   Format: { 'AAPL': [{ date: '2026-01-01', close: 150 }, ...], ... }
     * 
     * Algorithm:
     * 1. Simulate portfolio day-by-day from first to last transaction
     * 2. Update holdings when transactions occur
     * 3. Mark-to-market using last known price each day
     * 4. Track peak equity and compute drawdown
     */
    recomputeEquityCurve(priceSeriesBySymbol = {}) {
      const txs = [...this.transactions].sort(sortByDate)
      if (!txs.length) {
        this.equityCurve = []
        this.maxDrawdown = 0
        return
      }

      // Get all unique symbols from transactions
      const symbols = Array.from(
        new Set(txs.map((tx) => tx.symbol.toUpperCase()))
      )
      
      // Build price lookup maps for each symbol
      const priceMaps = new Map()
      let minDate = txs[0].date
      let maxDate = txs[txs.length - 1].date

      symbols.forEach((symbol) => {
        const series = priceSeriesBySymbol[symbol] || []
        const map = new Map()
        series.forEach((point) => {
          map.set(point.date, Number(point.close) || 0)
          // Extend date range if price data goes beyond transaction dates
          if (point.date < minDate) minDate = point.date
          if (point.date > maxDate) maxDate = point.date
        })
        priceMaps.set(symbol, map)
      })

      // Initialize holdings and price tracking
      const holdings = new Map(symbols.map((s) => [s, 0]))
      const lastClose = new Map(symbols.map((s) => [s, 0]))
      
      // Group transactions by date
      const byDate = txs.reduce((acc, tx) => {
        const key = tx.dateEntered || tx.date
        if (!acc[key]) acc[key] = []
        acc[key].push(tx)
        return acc
      }, {})

      // Simulate portfolio day by day
      const start = new Date(`${minDate}T00:00:00Z`)
      const end = new Date(`${maxDate}T00:00:00Z`)
      const curve = []
      let peak = 0
      let maxDrawdown = 0

      for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
        const date = d.toISOString().slice(0, 10)
        
        // Apply all transactions for this date
        const dayTxs = byDate[date] || []
        dayTxs.forEach((tx) => {
          const symbol = tx.symbol.toUpperCase()
          const qty = Number(tx.qty ?? tx.quantity) || 0
          const current = holdings.get(symbol) || 0
          if (tx.type === 'BUY') holdings.set(symbol, current + qty)
          if (tx.type === 'SELL') holdings.set(symbol, current - qty)
        })

        // Update last known prices
        symbols.forEach((symbol) => {
          const map = priceMaps.get(symbol)
          if (map?.has(date)) {
            lastClose.set(symbol, map.get(date))
          }
        })

        // Calculate total portfolio value (mark-to-market)
        let value = 0
        symbols.forEach((symbol) => {
          value += (holdings.get(symbol) || 0) * (lastClose.get(symbol) || 0)
        })
        
        // Track peak and drawdown
        if (value > peak) peak = value
        const drawdown = peak ? (value / peak) - 1 : 0
        if (drawdown < maxDrawdown) maxDrawdown = drawdown
        
        curve.push({ time: date, value, drawdown })
      }

      this.equityCurve = curve
      this.maxDrawdown = maxDrawdown
    },
  },
})
