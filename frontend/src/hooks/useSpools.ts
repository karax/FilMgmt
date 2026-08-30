import { useQuery } from '@tanstack/react-query'

import { getSpools } from '../api/spools'
import type { SpoolFilters } from '../types/spool'

export const spoolsQueryKey = ['spools'] as const

export function useSpools(filters: SpoolFilters = {}) {
  const hasFilters = Object.values(filters).some((value) => value !== undefined)
  return useQuery({
    queryKey: hasFilters ? [...spoolsQueryKey, filters] : spoolsQueryKey,
    queryFn: ({ signal }) => getSpools(filters, signal),
    staleTime: 30_000,
  })
}
