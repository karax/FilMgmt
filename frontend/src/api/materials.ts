import type { Material } from '../types/spool'
import { apiGet } from './client'

export function getMaterials(signal?: AbortSignal): Promise<Material[]> {
  return apiGet<Material[]>('/api/materials', signal)
}
