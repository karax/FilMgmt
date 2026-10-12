import { describe, expect, it } from 'vitest'

import { bucketForRange, formatCurrency, formatDuration, formatGrams, formatPercentage } from './analytics'

describe('analytics formatting', () => {
  it('formats grams and kilograms without prematurely rounding input', () => {
    expect(formatGrams('1310.070', 'en')).toBe('1.31 kg')
    expect(formatGrams('730.079', 'en')).toBe('730.1 g')
    expect(formatGrams('40819.930', 'en')).toBe('40.82 kg')
  })

  it('formats durations, currencies, and percentages for display', () => {
    expect(formatDuration(270321, 'en')).toBe('75h 5m')
    expect(formatCurrency('20.30', 'EUR', 'en')).toBe('€20.30')
    expect(formatPercentage('73.913', 'en')).toBe('73.91%')
    expect(formatPercentage(null, 'en')).toBe('—')
  })

  it('selects restrained buckets for each range without resolving date boundaries', () => {
    expect(bucketForRange('last_7_days')).toBe('day')
    expect(bucketForRange('last_90_days')).toBe('week')
    expect(bucketForRange('last_12_months')).toBe('month')
  })
})
