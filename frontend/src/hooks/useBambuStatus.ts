import { useQuery } from '@tanstack/react-query'

import { getBambuStatus } from '../api/bambu'

export const bambuStatusQueryKey = ['bambu-status'] as const

export function useBambuStatus() {
  return useQuery({
    queryKey: bambuStatusQueryKey,
    queryFn: ({ signal }) => getBambuStatus(signal),
    refetchInterval: 5_000,
    staleTime: 2_000,
  })
}
