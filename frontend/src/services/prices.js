export function getCloseOnOrBefore(asset, date) {
  if (!asset || !asset.dates || !asset.series) {
    return { error: 'Missing price history' }
  }
  const target = new Date(`${date}T00:00:00Z`)
  const dates = asset.dates
  let idx = -1
  for (let i = dates.length - 1; i >= 0; i -= 1) {
    if (new Date(`${dates[i]}T00:00:00Z`) <= target) {
      idx = i
      break
    }
  }
  if (idx === -1) {
    return { error: 'No price available before selected date' }
  }
  const close = Number(asset.series[idx])
  return {
    usedDate: dates[idx],
    close,
    provider: asset.provider || asset.cache_status || 'cache',
    freshness: asset.is_stale ? 'stale' : 'fresh',
  }
}
