import { beforeEach, describe, expect, it } from 'vitest'

import i18n from '../i18n'
import { makeSpool } from '../test/spoolFixture'
import {
  calculateInventorySummary,
  formatCurrency,
  formatDate,
  formatWeight,
  formatPercent,
  groupSpoolsByMaterial,
  sortCriticalSpools,
} from './inventory'

describe('inventory presentation calculations', () => {
  beforeEach(async () => { await i18n.changeLanguage('en') })
  const pla = makeSpool().material
  const petg = {
    ...makeSpool().material,
    id: 2,
    name: 'PETG',
    category: 'PETG',
  }

  const exampleSpools = [
    makeSpool({
      id: 1,
      code: 'FIL-0001',
      material: pla,
      current_filament_weight_g: '800.000',
      remaining_percent: 80,
      status: 'OPEN',
    }),
    makeSpool({
      id: 2,
      code: 'FIL-0002',
      material: pla,
      current_filament_weight_g: '150.000',
      remaining_percent: 15,
      status: 'LOW',
    }),
    makeSpool({
      id: 3,
      code: 'FIL-0003',
      material_id: 2,
      material: petg,
      current_filament_weight_g: '0.000',
      remaining_percent: 0,
      status: 'EMPTY',
      needs_drying: true,
    }),
  ]

  it('calculates totals from API-owned status and drying fields', () => {
    expect(calculateInventorySummary(exampleSpools)).toEqual({
      totalSpools: 3,
      totalWeightG: 950,
      lowCount: 1,
      emptyCount: 1,
      needsDryingCount: 1,
    })
  })

  it('groups counts and weight by stable material id', () => {
    expect(groupSpoolsByMaterial(exampleSpools)).toEqual([
      { material: pla, spoolCount: 2, totalWeightG: 950 },
      { material: petg, spoolCount: 1, totalWeightG: 0 },
    ])
  })

  it('orders empty before low before drying-only, then by percentage', () => {
    const drying = makeSpool({
      id: 4,
      code: 'FIL-0004',
      needs_drying: true,
      remaining_percent: 70,
    })
    const lowerLow = makeSpool({
      id: 5,
      code: 'FIL-0005',
      status: 'LOW',
      remaining_percent: 5,
    })

    expect(sortCriticalSpools([drying, exampleSpools[1], lowerLow, exampleSpools[2]]))
      .toHaveLength(4)
    expect(
      sortCriticalSpools([drying, exampleSpools[1], lowerLow, exampleSpools[2]]).map(
        (spool) => spool.code,
      ),
    ).toEqual(['FIL-0003', 'FIL-0005', 'FIL-0002', 'FIL-0004'])
  })

  it('formats grams and kilograms consistently', () => {
    expect(formatWeight(0)).toBe('0 g')
    expect(formatWeight(742)).toBe('742 g')
    expect(formatWeight(1500)).toBe('1.50 kg')
    expect(formatWeight(31450)).toBe('31.45 kg')
  })

  it('formats remaining percentage with one decimal place', () => {
    expect(formatPercent(80)).toBe('80.0%')
    expect(formatPercent(74.24)).toBe('74.2%')
  })

  it('uses the display locale without changing the stored currency', async () => {
    expect(formatCurrency(1234.5, 'EUR')).toMatch(/€.*1,234\.50/)
    expect(formatWeight(1500)).toBe('1.50 kg')
    expect(formatPercent(74.25)).toBe('74.3%')
    expect(formatDate('2026-09-13T12:00:00Z')).toMatch(/Sep/)

    await i18n.changeLanguage('pt-BR')
    expect(formatCurrency(1234.5, 'EUR')).toMatch(/€.*1\.234,50/)
    expect(formatWeight(1500)).toBe('1,50 kg')
    expect(formatPercent(74.25)).toBe('74,3%')
    expect(formatDate('2026-09-13T12:00:00Z')).toMatch(/set/i)
    expect(formatCurrency(12.5, 'USD')).toContain('US$')
  })
})
