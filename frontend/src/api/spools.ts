import type { Spool } from '../types/spool'
import { apiGet } from './client'

export function getSpools(signal?: AbortSignal): Promise<Spool[]> {
  return apiGet<Spool[]>('/api/spools', signal)
}
