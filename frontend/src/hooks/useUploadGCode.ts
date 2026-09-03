import { useMutation } from '@tanstack/react-query'

import { uploadGCode } from '../api/gcode'

export function useUploadGCode() {
  return useMutation({ mutationFn: uploadGCode })
}
