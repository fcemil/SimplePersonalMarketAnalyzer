<template>
  <div class="errors">
    <strong v-if="mode === 'mock'">Frontend running without backend data.</strong>
    <strong v-else>Some data could not be refreshed.</strong>
    <p v-if="mode === 'mock'">Add an `/api/assets` endpoint in Flask to provide real data.</p>
    <ul v-else>
      <li v-for="err in errors" :key="err">{{ err }}</li>
    </ul>
  </div>
</template>

<script setup>
// Warning banner shown when the API is unavailable or rate-limited.
const props = defineProps({
  mode: { type: String, default: 'mock' },
  errors: { type: Array, default: () => [] },
})
</script>
