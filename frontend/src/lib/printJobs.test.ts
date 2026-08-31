import { beforeEach, describe, expect, it } from 'vitest'

import i18n from '../i18n'
import { elapsedMinutes, formatDuration, formatPrintDateTime, jobsForStatus } from './printJobs'
import type { PrintJob } from '../types/printJob'

const job = (id: number, status: PrintJob['status'], created_at = '2026-08-30T10:00:00Z'): PrintJob => ({
  id, name: `Job ${id}`, status, spools: [{ id: 1, spool_id: 1, position: 0, estimated_weight_g: null, actual_weight_g: null, filament_cost_per_g: null, material_cost: null, material_cost_currency: null, created_at, updated_at: created_at }], total_estimated_weight_g: null, total_actual_weight_g: null,
  estimated_time_minutes: null, actual_time_minutes: null, printer_name: null, started_at: null,
  finished_at: null, notes: null, created_at, updated_at: created_at,
})

describe('print job formatters', () => {
  beforeEach(async () => { await i18n.changeLanguage('pt-BR') })

  it('formats durations including jobs longer than one day', () => {
    expect(formatDuration(null)).toBe('—')
    expect(formatDuration(45)).toBe('45 min')
    expect(formatDuration(90)).toBe('1h 30min')
    expect(formatDuration(1500)).toBe('25h')
  })

  it('calculates running durations without resetting after 24 hours and rejects invalid dates', () => {
    const now = new Date('2026-08-30T12:00:00Z').getTime()
    expect(formatDuration(elapsedMinutes('2026-08-30T11:45:00Z', now))).toBe('15 min')
    expect(formatDuration(elapsedMinutes('2026-08-30T10:30:00Z', now))).toBe('1h 30min')
    expect(formatDuration(elapsedMinutes('2026-08-29T09:45:00Z', now))).toBe('26h 15min')
    expect(formatDuration(elapsedMinutes('2026-08-27T12:00:00Z', now))).toBe('72h')
    expect(elapsedMinutes('not-a-date', now)).toBeNull()
  })

  it('keeps print-job status values intact while sorting the selected status', () => {
    const newer = job(2, 'PLANNED', '2026-08-30T11:00:00Z')
    const older = job(1, 'PLANNED')
    expect(jobsForStatus([older, newer, job(3, 'SUCCESS')], 'PLANNED')).toEqual([newer, older])
  })

  it('formats dates with the active locale and safely falls back for invalid values', async () => {
    const value = '2026-08-30T22:47:00Z'
    expect(formatPrintDateTime(value)).toMatch(/^\d{2}\/\d{2}\/2026/)
    expect(formatPrintDateTime('invalid')).toBe('—')
    await i18n.changeLanguage('en')
    expect(formatPrintDateTime(value)).toMatch(/^\d{2}\/\d{2}\/2026/)
    expect(formatPrintDateTime(value)).toMatch(/AM|PM/)
  })
})
