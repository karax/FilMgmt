import { isApiError } from '../api/client'

export const MAX_SPOOL_FILAMENT_WEIGHT_G = 2000
export const MAX_SPOOL_PURCHASE_PRICE = 100

export type SpoolFormField =
  | 'manufacturerId' | 'materialId' | 'displayName'
  | 'productName' | 'colorName' | 'colorHex' | 'diameter' | 'initialWeight'
  | 'currentWeight' | 'emptySpoolWeight' | 'purchasePrice' | 'storeName' | 'currency'
  | 'purchaseDate' | 'nozzleTempMin' | 'nozzleTempMax' | 'bedTempMin'
  | 'bedTempMax' | 'needsDrying' | 'lastDriedAt' | 'notes'

const fields: Record<string, SpoolFormField> = {
  display_name: 'displayName', manufacturer_id: 'manufacturerId', material_id: 'materialId',
  product_name: 'productName', color_name: 'colorName',
  color_hex: 'colorHex', diameter_mm: 'diameter', initial_filament_weight_g: 'initialWeight',
  current_filament_weight_g: 'currentWeight', empty_spool_weight_g: 'emptySpoolWeight',
  purchase_price: 'purchasePrice', store_name: 'storeName', currency: 'currency', purchase_date: 'purchaseDate',
  nozzle_temp_min: 'nozzleTempMin', nozzle_temp_max: 'nozzleTempMax',
  bed_temp_min: 'bedTempMin', bed_temp_max: 'bedTempMax', needs_drying: 'needsDrying',
  last_dried_at: 'lastDriedAt', notes: 'notes',
}

export type FastApiIssue = { loc?: unknown; msg?: unknown; type?: unknown }

export type ValidationMessageResolver = (issue: FastApiIssue) => string

const defaultMessage: ValidationMessageResolver = (issue) => (
  typeof issue.msg === 'string' ? issue.msg : 'Invalid value.'
)

export function mapSpoolApiValidationErrors(
  error: unknown,
  messageForIssue: ValidationMessageResolver = defaultMessage,
): {
  fieldErrors: Partial<Record<SpoolFormField, string>>
  formError: string | null
} | null {
  if (!isApiError(error) || error.status !== 422) return null
  const detail = error.detail && typeof error.detail === 'object' && 'detail' in error.detail
    ? (error.detail as { detail?: unknown }).detail
    : error.detail
  if (!Array.isArray(detail)) return { fieldErrors: {}, formError: null }

  const fieldErrors: Partial<Record<SpoolFormField, string>> = {}
  const rootMessages: string[] = []
  for (const issue of detail as FastApiIssue[]) {
    const loc = Array.isArray(issue.loc) ? issue.loc : []
    const rawField = [...loc].reverse().find((part): part is string => typeof part === 'string' && part !== 'body')
    const field = rawField ? fields[rawField] : undefined
    const message = messageForIssue(issue)
    if (field) fieldErrors[field] ??= message
    else rootMessages.push(message)
  }
  if (!Object.keys(fieldErrors).length && !rootMessages.length) return null
  return { fieldErrors, formError: rootMessages.join(' ') || null }
}
