import { describe, expect, it } from 'vitest'

import {
  calculateEstimatedMaterialCost,
  sumEstimatedCostsByCurrency,
} from './printCost'

describe('calculateEstimatedMaterialCost', () => {
  it.each([
    ['100', '2.0000'],
    ['250', '5.0000'],
    ['76.4', '1.5280'],
  ])('uses the canonical rounded unit cost for %s g', (weight, expected) => {
    expect(calculateEstimatedMaterialCost('20', '1000', weight)).toEqual({
      filamentCostPerG: '0.020000',
      materialCost: expected,
    })
  })

  it('matches the backend six-then-four decimal rounding rule', () => {
    expect(calculateEstimatedMaterialCost('29.99', '2500', '300')).toEqual({
      filamentCostPerG: '0.011996',
      materialCost: '3.5988',
    })
  })

  it('keeps unknown, empty, free, and zero-weight cases distinct', () => {
    expect(calculateEstimatedMaterialCost(null, '1000', '100')).toBeNull()
    expect(calculateEstimatedMaterialCost('20', '1000', '')).toBeNull()
    expect(calculateEstimatedMaterialCost('0', '1000', '100')).toEqual({
      filamentCostPerG: '0.000000',
      materialCost: '0.0000',
    })
    expect(calculateEstimatedMaterialCost('20', '1000', '0')).toEqual({
      filamentCostPerG: '0.020000',
      materialCost: '0.0000',
    })
  })

  it('rejects invalid values instead of inventing a cost', () => {
    expect(calculateEstimatedMaterialCost('20', '0', '100')).toBeNull()
    expect(calculateEstimatedMaterialCost('20', '1000', '-1')).toBeNull()
    expect(calculateEstimatedMaterialCost('not-a-price', '1000', '100')).toBeNull()
  })
})

describe('sumEstimatedCostsByCurrency', () => {
  it('adds same-currency costs using exact fixed-point arithmetic', () => {
    expect(sumEstimatedCostsByCurrency([
      { currency: 'EUR', materialCost: '2.5200' },
      { currency: 'EUR', materialCost: '1.8400' },
      { currency: 'EUR', materialCost: '0.7000' },
    ])).toEqual([{ currency: 'EUR', amount: '5.0600' }])
  })

  it('keeps different currencies in separate totals', () => {
    expect(sumEstimatedCostsByCurrency([
      { currency: 'USD', materialCost: '1.8400' },
      { currency: 'EUR', materialCost: '2.5200' },
    ])).toEqual([
      { currency: 'EUR', amount: '2.5200' },
      { currency: 'USD', amount: '1.8400' },
    ])
  })
})
