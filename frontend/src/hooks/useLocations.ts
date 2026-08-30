import { useQuery } from '@tanstack/react-query'

import { getLocations } from '../api/locations'

export const locationsQueryKey = ['locations'] as const

export function useLocations(enabled = true) {
  return useQuery({
    queryKey: locationsQueryKey,
    queryFn: ({ signal }) => getLocations(signal),
    staleTime: 5 * 60_000,
    enabled,
  })
}
