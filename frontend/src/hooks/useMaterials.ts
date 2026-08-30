import { useQuery } from '@tanstack/react-query'

import { getMaterials } from '../api/materials'

export const materialsQueryKey = ['materials'] as const

export function useMaterials(enabled = true) {
  return useQuery({
    queryKey: materialsQueryKey,
    queryFn: ({ signal }) => getMaterials(signal),
    staleTime: 5 * 60_000,
    enabled,
  })
}
