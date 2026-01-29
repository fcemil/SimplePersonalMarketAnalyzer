/**
 * Settings Store - User preferences and configuration.
 * 
 * Manages:
 * - Fee policy (percent-based or fixed fees)
 * - Quantity precision for decimal places
 * - Persistent storage in localStorage
 * 
 * Fee Policy Modes:
 * - PERCENT: Fee = price × quantity × percentFee (clamped to min/max)
 * - FIXED: Fee = constant amount per transaction
 */
import { defineStore } from 'pinia'

// localStorage key for persisting settings
const STORAGE_KEY = 'pm-settings'

// Default settings (used on first load or if localStorage is unavailable)
const defaults = {
  feePolicy: {
    mode: 'PERCENT',  // 'PERCENT' or 'FIXED'
    percentFee: 0.001,  // 0.1% default fee
    minFee: 1.0,  // Minimum fee in currency units
    maxFee: 10.0,  // Maximum fee in currency units
    currency: 'USD',
  },
  quantityPrecision: 6,  // Decimal places for share quantities
}

/**
 * Load settings from localStorage with fallback to defaults.
 * 
 * @returns {Object} Settings object
 */
function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaults
    // Merge with defaults to handle new settings added in updates
    return { ...defaults, ...JSON.parse(raw) }
  } catch (err) {
    return defaults
  }
}

export const useSettingsStore = defineStore('settings', {
  // Load initial state from localStorage
  state: () => loadSettings(),
  actions: {
    /**
     * Persist current state to localStorage.
     */
    persist() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.$state))
    },
    /**
     * Update fee policy settings.
     * 
     * @param {Object} next - Partial fee policy object to merge
     */
    updateFeePolicy(next) {
      this.feePolicy = { ...this.feePolicy, ...next }
      this.persist()
    },
    /**
     * Update quantity precision setting.
     * 
     * @param {number} value - Number of decimal places (0-10)
     */
    setQuantityPrecision(value) {
      this.quantityPrecision = value
      this.persist()
    },
  },
})
