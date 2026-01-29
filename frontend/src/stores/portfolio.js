import { defineStore } from 'pinia'
import { addTransaction, deleteTransaction, getAllTransactions, updateTransaction } from '../lib/idb'

function sortByDate(a, b) {
  const aDate = a.dateEntered || a.date || ''
  const bDate = b.dateEntered || b.date || ''
  if (aDate === bDate) return String(a.id || '').localeCompare(String(b.id || ''))
  return String(aDate).localeCompare(String(bDate))
}

export const usePortfolioStore = defineStore('portfolio', {
  state: () => ({
    transactions: [],
    positions: [],
    realizedPnL: 0,
    equityCurve: [],
    maxDrawdown: 0,
    lastLoadedAt: null,
  }),
  actions: {
    async loadTransactions() {
      const items = await getAllTransactions()
      const list = Array.isArray(items) ? items.filter(Boolean) : []
      const normalized = list.map((tx) => ({
        ...tx,
        id: tx?.id || crypto.randomUUID(),
      }))
      this.transactions = normalized.sort(sortByDate)
      this.recomputePositions()
      this.lastLoadedAt = Date.now()
    },
    async addTx(tx) {
      await addTransaction(tx)
      this.transactions = [...this.transactions, tx].sort(sortByDate)
      this.recomputePositions()
    },
    async editTx(tx) {
      await updateTransaction(tx)
      const next = this.transactions.map((item) => (item.id === tx.id ? tx : item))
      this.transactions = next.sort(sortByDate)
      this.recomputePositions()
    },
    async deleteTx(id) {
      await deleteTransaction(id)
      this.transactions = this.transactions.filter((item) => item.id !== id)
      this.recomputePositions()
    },
    async addBuySimple(tx) {
      await addTransaction(tx)
      this.transactions = [...this.transactions, tx].sort(sortByDate)
      this.recomputePositions()
    },
    async editBuySimple(tx) {
      await updateTransaction(tx)
      const next = this.transactions.map((item) => (item.id === tx.id ? tx : item))
      this.transactions = next.sort(sortByDate)
      this.recomputePositions()
    },
    recomputePositions(priceBySymbol = {}) {
      const positions = new Map()
      let realizedPnL = 0

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
          const newCostBasis = pos.costBasis + gross
          const newQty = pos.quantity + qty
          pos.quantity = newQty
          pos.costBasis = newCostBasis
          pos.avgCost = newQty ? newCostBasis / newQty : 0
        } else if (tx.type === 'SELL') {
          const sellQty = Math.min(pos.quantity, qty)
          realizedPnL += sellQty * (price - pos.avgCost) - fee
          const newQty = pos.quantity - sellQty
          pos.quantity = newQty
          pos.costBasis = pos.avgCost * newQty
        }
      })

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

      this.positions = mapped.filter((pos) => pos.quantity > 0)
      this.realizedPnL = realizedPnL
    },
    recomputeEquityCurve(priceSeriesBySymbol = {}) {
      const txs = [...this.transactions].sort(sortByDate)
      if (!txs.length) {
        this.equityCurve = []
        this.maxDrawdown = 0
        return
      }

      const symbols = Array.from(
        new Set(txs.map((tx) => tx.symbol.toUpperCase()))
      )
      const priceMaps = new Map()
      let minDate = txs[0].date
      let maxDate = txs[txs.length - 1].date

      symbols.forEach((symbol) => {
        const series = priceSeriesBySymbol[symbol] || []
        const map = new Map()
        series.forEach((point) => {
          map.set(point.date, Number(point.close) || 0)
          if (point.date < minDate) minDate = point.date
          if (point.date > maxDate) maxDate = point.date
        })
        priceMaps.set(symbol, map)
      })

      const holdings = new Map(symbols.map((s) => [s, 0]))
      const lastClose = new Map(symbols.map((s) => [s, 0]))
      const byDate = txs.reduce((acc, tx) => {
        const key = tx.dateEntered || tx.date
        if (!acc[key]) acc[key] = []
        acc[key].push(tx)
        return acc
      }, {})

      const start = new Date(`${minDate}T00:00:00Z`)
      const end = new Date(`${maxDate}T00:00:00Z`)
      const curve = []
      let peak = 0
      let maxDrawdown = 0

      for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
        const date = d.toISOString().slice(0, 10)
        const dayTxs = byDate[date] || []
        dayTxs.forEach((tx) => {
          const symbol = tx.symbol.toUpperCase()
          const qty = Number(tx.qty ?? tx.quantity) || 0
          const current = holdings.get(symbol) || 0
          if (tx.type === 'BUY') holdings.set(symbol, current + qty)
          if (tx.type === 'SELL') holdings.set(symbol, current - qty)
        })

        symbols.forEach((symbol) => {
          const map = priceMaps.get(symbol)
          if (map?.has(date)) {
            lastClose.set(symbol, map.get(date))
          }
        })

        let value = 0
        symbols.forEach((symbol) => {
          value += (holdings.get(symbol) || 0) * (lastClose.get(symbol) || 0)
        })
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
