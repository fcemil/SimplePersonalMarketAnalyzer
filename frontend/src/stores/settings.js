import { defineStore } from 'pinia'

const STORAGE_KEY = 'pm-settings'

const defaults = {
  feePolicy: {
    mode: 'PERCENT',
    percentFee: 0.001,
    minFee: 1.0,
    maxFee: 10.0,
    currency: 'USD',
  },
  quantityPrecision: 6,
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaults
    return { ...defaults, ...JSON.parse(raw) }
  } catch (err) {
    return defaults
  }
}

export const useSettingsStore = defineStore('settings', {
  state: () => loadSettings(),
  actions: {
    persist() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.$state))
    },
    updateFeePolicy(next) {
      this.feePolicy = { ...this.feePolicy, ...next }
      this.persist()
    },
    setQuantityPrecision(value) {
      this.quantityPrecision = value
      this.persist()
    },
  },
})
