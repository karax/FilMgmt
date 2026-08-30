import type { CreateSpoolPayload, Spool, SpoolFilters } from '../types/spool'
import { apiGet, apiPost } from './client'

export function getSpools(filters: SpoolFilters = {}, signal?: AbortSignal): Promise<Spool[]> {
  const params = new URLSearchParams()
  const values: Record<string, number | string | boolean | undefined> = {
    search: filters.search,
    manufacturer_id: filters.manufacturerId,
    material_id: filters.materialId,
    location_id: filters.locationId,
    status: filters.status,
    needs_drying: filters.needsDrying,
    min_weight_g: filters.minWeightG,
    max_weight_g: filters.maxWeightG,
    min_remaining_percent: filters.minRemainingPercent,
    max_remaining_percent: filters.maxRemainingPercent,
    include_archived: filters.includeArchived,
  }
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined) params.set(key, String(value))
  }
  const query = params.toString()
  return apiGet<Spool[]>(`/api/spools${query ? `?${query}` : ''}`, signal)
}

export function getSpool(code: string, signal?: AbortSignal): Promise<Spool> {
  return apiGet<Spool>(`/api/spools/${encodeURIComponent(code)}`, signal)
}

export function createSpool(payload: CreateSpoolPayload): Promise<Spool> {
  return apiPost<Spool, CreateSpoolPayload>('/api/spools', payload)
}
