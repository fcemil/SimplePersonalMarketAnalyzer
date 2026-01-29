/**
 * Fee calculation utilities.
 * 
 * Supports multiple fee models:
 * - NONE: No fees
 * - FIXED: Constant fee per transaction
 * - PERCENT: Percentage-based fee with min/max bounds
 */

/**
 * Calculate transaction fee based on fee policy.
 * 
 * @param {number} gross - Gross transaction amount (price × quantity)
 * @param {Object} policy - Fee policy configuration
 * @param {string} policy.mode - Fee mode: 'NONE', 'FIXED', or 'PERCENT'
 * @param {number} policy.fixedFee - Fixed fee amount (for FIXED mode)
 * @param {number} policy.percentFee - Fee percentage (for PERCENT mode)
 * @param {number} policy.minFee - Minimum fee (for PERCENT mode)
 * @param {number} policy.maxFee - Maximum fee (for PERCENT mode)
 * 
 * @returns {number} Calculated fee amount
 * 
 * Examples:
 *   computeFee(1000, { mode: 'FIXED', fixedFee: 5 }) => 5
 *   computeFee(1000, { mode: 'PERCENT', percentFee: 0.001, minFee: 1, maxFee: 10 }) => 1 (clamped to min)
 */
export function computeFee(gross, policy) {
  const amount = Number(gross) || 0
  
  // No fee mode
  if (!policy || policy.mode === 'NONE') return 0
  
  // Fixed fee mode: return fixed amount (capped at gross to avoid negative net)
  if (policy.mode === 'FIXED') return Math.min(amount, Number(policy.fixedFee) || 0)
  
  // Percentage-based fee with min/max bounds
  if (policy.mode === 'PERCENT') {
    const pct = Number(policy.percentFee) || 0
    const min = Number(policy.minFee) || 0
    const max = policy.maxFee !== undefined ? Number(policy.maxFee) : null
    
    // Calculate percentage fee
    let fee = amount * pct
    
    // Apply minimum bound
    if (fee < min) fee = min
    
    // Apply maximum bound if specified
    if (max !== null && fee > max) fee = max
    
    // Cap fee at gross amount to avoid negative net
    return Math.min(amount, fee)
  }
  
  return 0
}
