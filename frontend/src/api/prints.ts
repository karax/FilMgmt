import { apiGet, apiPatch, apiPost, apiPostWithoutBody } from './client'
import type { PrintJob, PrintJobFilters, PrintJobFinishPayload, PrintJobPayload, UpdatePrintJobPayload } from '../types/printJob'

export function getPrintJobs(filters: PrintJobFilters = {}, signal?: AbortSignal): Promise<PrintJob[]> {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.spoolId !== undefined) params.set('spool_id', String(filters.spoolId))
  const query = params.toString()
  return apiGet<PrintJob[]>(`/api/prints${query ? `?${query}` : ''}`, signal)
}

export function getPrintJob(id: number, signal?: AbortSignal): Promise<PrintJob> {
  return apiGet<PrintJob>(`/api/prints/${id}`, signal)
}

export function createPrintJob(payload: PrintJobPayload): Promise<PrintJob> {
  return apiPost<PrintJob, PrintJobPayload>('/api/prints', payload)
}

export function updatePrintJob(id: number, payload: UpdatePrintJobPayload): Promise<PrintJob> {
  return apiPatch<PrintJob, UpdatePrintJobPayload>(`/api/prints/${id}`, payload)
}

export function startPrintJob(id: number): Promise<PrintJob> {
  return apiPostWithoutBody<PrintJob>(`/api/prints/${id}/start`)
}

export function finishPrintJob(id: number, payload: PrintJobFinishPayload): Promise<PrintJob> {
  return apiPost<PrintJob, PrintJobFinishPayload>(`/api/prints/${id}/finish`, payload)
}
