import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  confirmReconciliation,
  getPendingReconciliation,
  undoReconciliation,
} from '../api/reconciliation'
import type { ReconciliationConfirmItem } from '../types/reconciliation'

export function useReconciliationQueue() {
  return useQuery({
    queryKey: ['reconciliation', 'pending'],
    queryFn: ({ signal }) => getPendingReconciliation(signal),
  })
}

export function useConfirmReconciliation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (items: ReconciliationConfirmItem[]) => confirmReconciliation(items),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['reconciliation'] }),
        queryClient.invalidateQueries({ queryKey: ['spools'] }),
        queryClient.invalidateQueries({ queryKey: ['prints'] }),
      ])
    },
  })
}

export function useUndoReconciliation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ usageId, reason }: { usageId: number; reason: string }) =>
      undoReconciliation(usageId, reason),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['reconciliation'] }),
        queryClient.invalidateQueries({ queryKey: ['spools'] }),
        queryClient.invalidateQueries({ queryKey: ['prints'] }),
      ])
    },
  })
}
