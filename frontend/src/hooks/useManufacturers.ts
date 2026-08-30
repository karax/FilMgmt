import { useQuery } from '@tanstack/react-query'

import { getManufacturers } from '../api/manufacturers'

export const manufacturersQueryKey = ['manufacturers'] as const

export function useManufacturers(enabled = true) {
  return useQuery({
    queryKey: manufacturersQueryKey,
    queryFn: ({ signal }) => getManufacturers(signal),
    staleTime: 5 * 60_000,
    enabled,
  })
}
