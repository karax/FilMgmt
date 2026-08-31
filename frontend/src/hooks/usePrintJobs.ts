import { useQuery } from '@tanstack/react-query'

import { getPrintJobs } from '../api/prints'
import type { PrintJobFilters } from '../types/printJob'

export const printJobsQueryKey = ['prints'] as const

export function usePrintJobs(filters: PrintJobFilters = {}) {
  const hasFilters = Object.values(filters).some((value) => value !== undefined)
  return useQuery({
    queryKey: hasFilters ? [...printJobsQueryKey, filters] : printJobsQueryKey,
    queryFn: ({ signal }) => getPrintJobs(filters, signal),
    staleTime: 30_000,
  })
}
