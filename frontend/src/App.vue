<template>
  <header class="app-header">
    <div>
      <h1>Personal Market Analyzer</h1>
      <p class="subtitle">Signals, charting, and portfolio decisions in one workspace.</p>
    </div>
    <nav class="tabs">
      <RouterLink to="/" class="tab" exact-active-class="active">Home</RouterLink>
      <RouterLink to="/analyze" class="tab" exact-active-class="active">Analyze</RouterLink>
      <RouterLink to="/portfolio" class="tab" exact-active-class="active">Portfolio</RouterLink>
      <RouterLink to="/simulate" class="tab" exact-active-class="active">Simulation</RouterLink>
    </nav>
  </header>

  <RouterView />
</template>
