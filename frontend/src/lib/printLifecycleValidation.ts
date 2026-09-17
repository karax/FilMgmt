import { isApiError } from '../api/client'
import type { PrintJobFinishPayload } from '../types/printJob'

type FastApiIssue = { loc?: unknown; msg?: unknown }

export function responseDetail(error: unknown): unknown {
  if (!isApiError(error)) return null
  if (error.detail && typeof error.detail === 'object' && 'detail' in error.detail) {
    return (error.detail as { detail?: unknown }).detail
  }
  return error.detail
}

export function apiDetailMessage(error: unknown): string | null {
  const detail = responseDetail(error)
  return typeof detail === 'string' ? detail : null
}

export function mapFinishValidationErrors(
  error: unknown,
  payload: PrintJobFinishPayload,
  validationMessage = 'Invalid consumption.',
): Map<number, string> {
  if (!isApiError(error) || error.status !== 422) return new Map()
  const detail = responseDetail(error)
  if (!Array.isArray(detail)) return new Map()

  const errors = new Map<number, string>()
  for (const issue of detail as FastApiIssue[]) {
    const location = Array.isArray(issue.loc) ? issue.loc : []
    const consumptionsIndex = location.findIndex((part) => part === 'consumptions')
    const index = location[consumptionsIndex + 1]
    if (consumptionsIndex < 0 || typeof index !== 'number') continue
    const consumption = payload.consumptions[index]
    if (!consumption) continue
    errors.set(consumption.spool_id, validationMessage)
  }
  return errors
}
