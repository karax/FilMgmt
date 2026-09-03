import { describe, expect, it } from 'vitest'

import { formatGCodeDuration } from './gcodeTime'

describe('G-code duration formatter', () => {
  it('formats seconds and minutes in both languages', () => {
    expect(formatGCodeDuration(42, 'pt-BR')).toBe('42 s')
    expect(formatGCodeDuration(42, 'en')).toBe('42 sec')
    expect(formatGCodeDuration(300, 'pt-BR')).toBe('5 min')
    expect(formatGCodeDuration(300, 'en')).toBe('5 min')
  })

  it('formats hours without treating a duration as a calendar date', () => {
    expect(formatGCodeDuration(4320, 'pt-BR')).toBe('1 h 12 min')
    expect(formatGCodeDuration(4320, 'en')).toBe('1 hr 12 min')
    expect(formatGCodeDuration(98_400, 'pt-BR')).toBe('1 d 3 h 20 min')
    expect(formatGCodeDuration(98_400, 'en')).toBe('1 d 3 hr 20 min')
  })

  it('rejects invalid durations', () => {
    expect(formatGCodeDuration(Number.NaN, 'en')).toBe('—')
    expect(formatGCodeDuration(-1, 'en')).toBe('—')
  })
})
