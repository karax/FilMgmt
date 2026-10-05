import type { Material } from '../types/spool'
import { apiDelete, apiGet, apiPost, apiPut } from './client'

export interface MaterialPayload {
  name: string
  category: string
  default_nozzle_temp_min: number | null
  default_nozzle_temp_max: number | null
  default_bed_temp_min: number | null
  default_bed_temp_max: number | null
  density_g_cm3: number | null
  notes: string | null
}

export function getMaterials(signal?: AbortSignal): Promise<Material[]> {
  return apiGet<Material[]>('/api/materials', signal)
}

export function createMaterial(payload: MaterialPayload): Promise<Material> {
  return apiPost('/api/materials', payload)
}

export function updateMaterial(id: number, payload: MaterialPayload): Promise<Material> {
  return apiPut(`/api/materials/${id}`, payload)
}

export function deleteMaterial(id: number): Promise<void> {
  return apiDelete(`/api/materials/${id}`)
}
