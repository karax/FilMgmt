import type { Location } from '../types/spool'
import { apiGet } from './client'

export function getLocations(signal?: AbortSignal): Promise<Location[]> {
  return apiGet<Location[]>('/api/locations', signal)
}
