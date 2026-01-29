<template>
  <section class="cards">
    <div class="card">
      <h3>Total Assets</h3>
      <div class="value">{{ total }}</div>
    </div>
    <div class="card">
      <h3>Bullish</h3>
      <div class="value">{{ counts.bullish || 0 }}</div>
    </div>
    <div class="card">
      <h3>Neutral</h3>
      <div class="value">{{ counts.neutral || 0 }}</div>
    </div>
    <div class="card">
      <h3>Bearish</h3>
      <div class="value">{{ counts.bearish || 0 }}</div>
    </div>
  </section>
</template>

<script setup>
// Summary metrics for quick scanning.
const props = defineProps({
  total: { type: Number, required: true },
  counts: { type: Object, required: true },
})
</script>
