import { useQuery } from '@tanstack/react-query'

import { estimateGCodeTime } from '../api/gcode'

export function useEstimateGCodeTime(uploadId: string) {
  return useQuery({
    queryKey: ['gcode-time', uploadId],
    queryFn: () => estimateGCodeTime(uploadId),
    enabled: Boolean(uploadId),
    retry: false,
  })
}
