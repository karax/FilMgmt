import { useQuery } from '@tanstack/react-query'

import { getPrintJob } from '../api/prints'

export function printJobQueryKey(id: number) {
  return ['print', id] as const
}

export function usePrintJob(id: number | undefined) {
  return useQuery({
    queryKey: printJobQueryKey(id ?? 0),
    queryFn: ({ signal }) => getPrintJob(id!, signal),
    enabled: id !== undefined && Number.isInteger(id) && id > 0,
    staleTime: 30_000,
  })
}
