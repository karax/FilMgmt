import type { Manufacturer } from '../types/spool'
import { apiGet } from './client'

export function getManufacturers(signal?: AbortSignal): Promise<Manufacturer[]> {
  return apiGet<Manufacturer[]>('/api/manufacturers', signal)
}
