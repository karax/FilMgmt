import { describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import { mapSpoolApiValidationErrors } from './spoolValidation'

describe('mapSpoolApiValidationErrors', () => {
  it('removes FastAPI body prefixes and maps known spool fields', () => {
    const result = mapSpoolApiValidationErrors(new ApiError('invalid', 422, {
      detail: [
        { loc: ['body', 'nozzle_temp_min'], msg: 'Invalid temperature' },
        { loc: ['body', 'color_hex'], msg: 'Invalid color' },
      ],
    }))
    expect(result?.fieldErrors).toEqual({ nozzleTempMin: 'Invalid temperature', colorHex: 'Invalid color' })
  })

  it('maps an API-shaped error after a hot-module update', () => {
    const result = mapSpoolApiValidationErrors({
      status: 422,
      detail: { detail: [{ loc: ['body', 'color_hex'], msg: 'Invalid color' }] },
    })

    expect(result).toEqual({
      fieldErrors: { colorHex: 'Invalid color' },
      formError: null,
    })
  })

  it('keeps root validation errors visible as form errors', () => {
    const result = mapSpoolApiValidationErrors(new ApiError('invalid', 422, {
      detail: [{ loc: ['body'], msg: 'nozzle temperature minimum cannot exceed maximum' }],
    }))
    expect(result?.formError).toContain('minimum cannot exceed maximum')
  })
})
