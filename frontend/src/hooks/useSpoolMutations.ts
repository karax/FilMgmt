import { useMutation, useQueryClient } from '@tanstack/react-query'

import { archiveSpool, deleteSpool, updateSpool } from '../api/spools'
import type { UpdateSpoolPayload } from '../types/spool'
import { spoolQueryKey } from './useSpool'
import { spoolsQueryKey } from './useSpools'

type UpdateInput = { code: string; payload: UpdateSpoolPayload }

function useInvalidateSpools() {
  const queryClient = useQueryClient()
  return async (code?: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: spoolsQueryKey }),
      ...(code ? [queryClient.invalidateQueries({ queryKey: spoolQueryKey(code) })] : []),
    ])
  }
}

export function useUpdateSpool() {
  const invalidate = useInvalidateSpools()
  return useMutation({
    mutationFn: ({ code, payload }: UpdateInput) => updateSpool(code, payload),
    onSuccess: async (spool) => invalidate(spool.code),
  })
}

export function useArchiveSpool() {
  const invalidate = useInvalidateSpools()
  return useMutation({
    mutationFn: archiveSpool,
    onSuccess: async (spool) => invalidate(spool.code),
  })
}

export function useDeleteSpool() {
  const invalidate = useInvalidateSpools()
  return useMutation({
    mutationFn: deleteSpool,
    onSuccess: async (_result, code) => invalidate(code),
  })
}
