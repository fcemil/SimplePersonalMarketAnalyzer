<template>
  <section class="quota">
    <div class="quota-card">
      <h3>Alpha Budget</h3>
      <div class="value">{{ usage.alpha.usedToday }} / {{ usage.alpha.budget }}</div>
      <p>{{ usage.alpha.usedLastMinute }} calls in last minute</p>
    </div>
    <div class="quota-card">
      <h3>Cache Hit Rate</h3>
      <div class="value">{{ formatPercent(usage.cache.hitRate) }}</div>
      <p>Across this session</p>
    </div>
    <div class="quota-card">
      <h3>Stooq Failures</h3>
      <div class="value">{{ usage.stooq.failures }}</div>
      <p>Since last reset</p>
    </div>
  </section>
</template>

<script setup>
const props = defineProps({
  usage: { type: Object, required: true },
})

function formatPercent(value) {
  if (typeof value !== 'number') return '--'
  return `${(value * 100).toFixed(0)}%`
}
</script>
