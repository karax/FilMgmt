import { useQuery } from '@tanstack/react-query'

import { getSpools } from '../api/spools'

export const spoolsQueryKey = ['spools'] as const

export function useSpools() {
  return useQuery({
    queryKey: spoolsQueryKey,
    queryFn: ({ signal }) => getSpools(signal),
    staleTime: 30_000,
  })
}
