import { useQuery } from '@tanstack/react-query'

import { getSpool } from '../api/spools'

export function spoolQueryKey(code: string) {
  return ['spool', code] as const
}

export function useSpool(code: string | undefined) {
  return useQuery({
    queryKey: spoolQueryKey(code ?? ''),
    queryFn: ({ signal }) => getSpool(code!, signal),
    enabled: Boolean(code),
    staleTime: 30_000,
  })
}
