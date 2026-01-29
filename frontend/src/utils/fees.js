export function computeFee(gross, policy) {
  const amount = Number(gross) || 0
  if (!policy || policy.mode === 'NONE') return 0
  if (policy.mode === 'FIXED') return Math.min(amount, Number(policy.fixedFee) || 0)
  if (policy.mode === 'PERCENT') {
    const pct = Number(policy.percentFee) || 0
    const min = Number(policy.minFee) || 0
    const max = policy.maxFee !== undefined ? Number(policy.maxFee) : null
    let fee = amount * pct
    if (fee < min) fee = min
    if (max !== null && fee > max) fee = max
    return Math.min(amount, fee)
  }
  return 0
}
