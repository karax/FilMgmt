import { useMutation } from '@tanstack/react-query'

import { parseGCode } from '../api/gcode'

export function useParseGCode() {
  return useMutation({ mutationFn: parseGCode })
}
