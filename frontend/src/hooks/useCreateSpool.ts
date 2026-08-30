import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createSpool } from '../api/spools'
import type { CreateSpoolPayload } from '../types/spool'
import { spoolsQueryKey } from './useSpools'

export function useCreateSpool() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreateSpoolPayload) => createSpool(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: spoolsQueryKey })
    },
  })
}
