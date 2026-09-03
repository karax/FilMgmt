import { useMutation } from '@tanstack/react-query'

import { calculateGCodeWeight } from '../api/gcode'
import type { GCodeWeightRequest } from '../types/gcode'

export function useCalculateGCodeWeight(uploadId: string) {
  return useMutation({
    mutationFn: (payload: GCodeWeightRequest) => calculateGCodeWeight(uploadId, payload),
  })
}
