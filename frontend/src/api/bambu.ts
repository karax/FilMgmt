import type { BambuStatus } from '../types/bambu'
import { apiGet } from './client'

export function getBambuStatus(signal?: AbortSignal): Promise<BambuStatus> {
  return apiGet<BambuStatus>('/api/integrations/bambu/status', signal)
}
