import { useMutation, useQueryClient } from '@tanstack/react-query'

import { finishPrintJob, createPrintJob, startPrintJob, updatePrintJob } from '../api/prints'
import { isApiError } from '../api/client'
import type { PrintJobFinishPayload, PrintJobPayload, UpdatePrintJobPayload } from '../types/printJob'
import { printJobQueryKey } from './usePrintJob'
import { printJobsQueryKey } from './usePrintJobs'
import { spoolQueryKey } from './useSpool'
import { spoolsQueryKey } from './useSpools'

type UpdateInput = { id: number; payload: UpdatePrintJobPayload }
type StartInput = { id: number; spoolCodes: string[] }
type FinishInput = { id: number; payload: PrintJobFinishPayload; spoolCodes: string[] }

function useInvalidatePrints() {
  const queryClient = useQueryClient()
  return async (id?: number) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: printJobsQueryKey }),
      ...(id === undefined ? [] : [queryClient.invalidateQueries({ queryKey: printJobQueryKey(id) })]),
    ])
  }
}

function useInvalidatePrintLifecycle() {
  const queryClient = useQueryClient()
  return async (id: number, spoolCodes: string[]) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: printJobsQueryKey }),
      queryClient.invalidateQueries({ queryKey: printJobQueryKey(id) }),
      queryClient.invalidateQueries({ queryKey: spoolsQueryKey }),
      ...spoolCodes.map((code) => queryClient.invalidateQueries({ queryKey: spoolQueryKey(code) })),
    ])
  }
}


export function useCreatePrintJob() {
  const invalidate = useInvalidatePrints()
  return useMutation({ mutationFn: createPrintJob, onSuccess: () => invalidate() })
}

export function useUpdatePrintJob() {
  const invalidate = useInvalidatePrints()
  return useMutation({
    mutationFn: ({ id, payload }: UpdateInput) => updatePrintJob(id, payload),
    onSuccess: (printJob) => invalidate(printJob.id),
  })
}

export function useStartPrintJob() {
  const invalidate = useInvalidatePrintLifecycle()
  return useMutation({
    mutationFn: ({ id }: StartInput) => startPrintJob(id),
    onSuccess: (printJob, input) => invalidate(printJob.id, input.spoolCodes),
    onError: (error, input) => isApiError(error) && error.status === 409
      ? invalidate(input.id, input.spoolCodes)
      : undefined,
  })
}

export function useFinishPrintJob() {
  const invalidate = useInvalidatePrintLifecycle()
  return useMutation({
    mutationFn: ({ id, payload }: FinishInput) => finishPrintJob(id, payload),
    onSuccess: (printJob, input) => invalidate(printJob.id, input.spoolCodes),
    onError: (error, input) => isApiError(error) && error.status === 409
      ? invalidate(input.id, input.spoolCodes)
      : undefined,
  })
}
