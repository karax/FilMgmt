import { useQuery } from '@tanstack/react-query'

import { detectGCodeMaterial } from '../api/gcode'

export function useDetectGCodeMaterial(uploadId: string) {
  return useQuery({
    queryKey: ['gcode-material-detection', uploadId],
    queryFn: () => detectGCodeMaterial(uploadId),
    enabled: Boolean(uploadId),
    retry: false,
  })
}
