import { apiGet, apiPost } from './client'
import type {
  ReconciliationConfirmItem,
  ReconciliationConfirmResult,
  ReconciliationJob,
  ReconciliationQueue,
} from '../types/reconciliation'

export function getPendingReconciliation(signal?: AbortSignal): Promise<ReconciliationQueue> {
  return apiGet<ReconciliationQueue>('/api/reconciliation/pending', signal)
}

export function confirmReconciliation(
  items: ReconciliationConfirmItem[],
): Promise<ReconciliationConfirmResult> {
  return apiPost<ReconciliationConfirmResult, { items: ReconciliationConfirmItem[] }>(
    '/api/reconciliation/confirm',
    { items },
  )
}

export function undoReconciliation(
  filamentUsageId: number,
  reason: string,
): Promise<ReconciliationJob> {
  return apiPost<ReconciliationJob, { reason: string }>(
    `/api/reconciliation/usages/${filamentUsageId}/undo`,
    { reason },
  )
}
