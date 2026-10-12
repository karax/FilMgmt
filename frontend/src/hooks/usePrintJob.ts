import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getPrintJob, requestPrintJobEnrichment } from '../api/prints'
import { printJobsQueryKey } from './usePrintJobs'

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

export function useRequestPrintJobEnrichment(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => requestPrintJobEnrichment(id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: printJobQueryKey(id) }),
        queryClient.invalidateQueries({ queryKey: printJobsQueryKey }),
      ])
    },
  })
}
