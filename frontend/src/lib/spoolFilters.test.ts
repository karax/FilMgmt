import { describe, expect, it } from 'vitest'

import { filtersFromSearchParams, filtersToSearchParams } from './spoolFilters'

describe('spool filter URL conversion', () => {
  it('serializes supported filters with API parameter names', () => {
    expect(filtersToSearchParams({ materialId: 2, status: 'LOW', needsDrying: false }).toString()).toBe('material_id=2&status=LOW&needs_drying=false')
  })

  it('trims search and encodes special characters safely', () => {
    const params = filtersToSearchParams({ search: '  PLA+  ', status: 'LOW' })
    expect(params.toString()).toBe('search=PLA%2B&status=LOW')
    expect(filtersFromSearchParams(new URLSearchParams('search=%20black%20')).search).toBe('black')
  })

  it('ignores invalid manual URL values', () => {
    expect(filtersFromSearchParams(new URLSearchParams('status=SUPER_LOW&min_remaining_percent=banana&max_remaining_percent=110'))).toEqual({})
  })
})
