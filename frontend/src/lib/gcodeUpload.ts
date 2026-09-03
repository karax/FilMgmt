export const DEFAULT_GCODE_MAX_UPLOAD_BYTES = 100 * 1024 * 1024

const configuredMaxUploadBytes = Number(import.meta.env.VITE_GCODE_MAX_UPLOAD_BYTES)
export const GCODE_MAX_UPLOAD_BYTES = (
  Number.isSafeInteger(configuredMaxUploadBytes) && configuredMaxUploadBytes > 0
    ? configuredMaxUploadBytes
    : DEFAULT_GCODE_MAX_UPLOAD_BYTES
)

export type GCodeFileValidationError = 'invalidExtension' | 'emptyFile' | 'tooLarge'

export function validateGCodeFile(
  file: File,
  maxUploadBytes = GCODE_MAX_UPLOAD_BYTES,
): GCodeFileValidationError | null {
  if (!file.name.toLowerCase().endsWith('.gcode')) return 'invalidExtension'
  if (file.size === 0) return 'emptyFile'
  if (file.size > maxUploadBytes) return 'tooLarge'
  return null
}

export function formatFileSize(sizeBytes: number, locale: string): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`

  const units = ['KB', 'MB', 'GB'] as const
  let value = sizeBytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }

  return `${new Intl.NumberFormat(locale, {
    maximumFractionDigits: 1,
    minimumFractionDigits: value < 10 ? 1 : 0,
  }).format(value)} ${units[unitIndex]}`
}
