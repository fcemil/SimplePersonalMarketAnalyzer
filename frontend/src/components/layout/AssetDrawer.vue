<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  asset: { type: Object, default: null },
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'set-stooq-symbol'])
const stooqDraft = ref('')

watch(
  () => props.asset,
  (next) => {
    if (!next) return
    stooqDraft.value = next.source_symbol || ''
  }
)

const strength = computed(() => {
  const score = Number(props.asset?.score || 0)
  return Math.min(100, Math.round(Math.abs(score) * 25))
})

const confidence = computed(() => {
  const sample = props.asset?.sample_count || 0
  const window = props.asset?.analysis_window_days || 30
  if (!sample) return 'Low'
  if (sample >= window * 3) return 'High'
  if (sample >= window * 2) return 'Medium'
  return 'Low'
})

const topContributions = computed(() => {
  const list = props.asset?.feature_contributions || []
  return [...list].sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact)).slice(0, 3)
})

const warnings = computed(() => {
  const items = []
  if (!props.asset) return items
  if (props.asset.is_stale) items.push('Stale cache in use')
  if (props.asset.sample_count && props.asset.analysis_window_days && props.asset.sample_count < props.asset.analysis_window_days) {
    items.push('Low sample count for analysis window')
  }
  if (!props.asset.series?.length && !props.asset.ohlc?.length) items.push('Missing chart data')
  return items
})

function submitStooq() {
  if (!props.asset?.symbol) return
  if (!stooqDraft.value.trim()) return
  emit('set-stooq-symbol', props.asset.symbol, stooqDraft.value.trim())
}
</script>

<template>
  <div class="drawer" :class="{ open }">
    <div class="drawer-header">
      <div>
        <h3>{{ asset?.name || 'Asset details' }}</h3>
        <p class="drawer-subtitle">{{ asset?.symbol }} · {{ asset?.type }}</p>
      </div>
      <button class="btn icon secondary" @click="$emit('close')">Close</button>
    </div>

    <div v-if="asset" class="drawer-body">
      <div class="drawer-metrics">
        <div>
          <span class="label">Signal Strength</span>
          <strong>{{ strength }}</strong>
        </div>
        <div>
          <span class="label">Confidence</span>
          <strong>{{ confidence }}</strong>
        </div>
        <div>
          <span class="label">Provider</span>
          <strong>{{ asset.provider || '—' }}</strong>
        </div>
      </div>

      <div class="drawer-section">
        <h4>Top Feature Contributions</h4>
        <ul>
          <li v-for="item in topContributions" :key="item.feature">
            {{ item.feature }}: {{ item.impact > 0 ? '+' : '' }}{{ item.impact }}
          </li>
        </ul>
      </div>

      <div v-if="warnings.length" class="drawer-section warning">
        <h4>Warnings</h4>
        <ul>
          <li v-for="warning in warnings" :key="warning">{{ warning }}</li>
        </ul>
      </div>

      <div
        v-if="asset.type === 'stock' && asset.stooq_error === 'symbol_not_found'"
        class="drawer-section"
      >
        <h4>Stooq Symbol Mapping</h4>
        <div class="mapping-inline">
          <input
            class="search-input"
            type="text"
            v-model="stooqDraft"
            placeholder="Set Stooq symbol (e.g. aapl.us)"
          />
          <button class="btn secondary" @click="submitStooq">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>
