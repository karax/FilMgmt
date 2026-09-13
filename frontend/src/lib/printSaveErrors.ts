import type { TFunction } from 'i18next'
import { isApiError } from '../api/client'
import { responseDetail } from './printLifecycleValidation'
import type { FastApiIssue } from './spoolValidation'

export type SaveRow = { key: number; spoolId: string }
export type PrintSaveErrors = { formError: string; fieldErrors: Record<string, string> }

export function shouldRefreshPrintSpools(error: unknown): boolean {
  if (!isApiError(error)) return false
  const detail = responseDetail(error)
  const code = detail && typeof detail === 'object' && 'code' in detail ? detail.code : null
  return (error.status === 409 && code !== 'print_not_planned')
    || (error.status === 404 && code === 'spool_not_found')
}

// Exact API paths only. Submitted indexes become stable keys so row removal
// cannot shift an error onto a different spool.
export function normalizePrintSaveError(error: unknown, rows: SaveRow[], t: TFunction): PrintSaveErrors {
  const fieldErrors: Record<string, string> = {}
  const result = (key: string): PrintSaveErrors => ({ formError: t(`prints.form.${key}`), fieldErrors })
  if (!isApiError(error)) return result(error instanceof TypeError ? 'networkError' : 'unexpectedError')
  if (error.status >= 500) return result('serverError')
  const detail = responseDetail(error)
  if (error.status === 422 && Array.isArray(detail)) {
    let unknown = false
    for (const raw of detail) {
      if (!raw || typeof raw !== 'object') { unknown = true; continue }
      const issue = raw as FastApiIssue
      const loc = Array.isArray(issue.loc) ? [...issue.loc] : []
      if (loc[0] === 'body') loc.shift()
      let field: string | undefined
      if (loc.length === 1 && ['name', 'printer_name', 'notes', 'estimated_time_minutes'].includes(loc[0])) field = loc[0]
      if (loc.length === 3 && loc[0] === 'spools' && Number.isInteger(loc[1]) && rows[loc[1]] && ['spool_id', 'estimated_weight_g'].includes(loc[2])) field = `spools.${rows[loc[1]].key}.${loc[2]}`
      if (!field) { unknown = true; continue }
      let message = t('prints.form.invalidValue')
      if (issue.type === 'missing' || issue.type === 'string_too_short') message = t('prints.form.requiredValue')
      if (issue.type === 'string_too_long') message = t('prints.form.tooLong')
      if (issue.type === 'greater_than') message = t('prints.form.positiveValue')
      if (issue.type === 'decimal_max_places') message = t('prints.form.decimalPlaces')
      if (field.endsWith('.spool_id')) message = t('prints.form.invalidSpool')
      fieldErrors[field] ??= message
    }
    return result(unknown || !Object.keys(fieldErrors).length ? 'validationError' : 'correctFields')
  }
  const code = detail && typeof detail === 'object' && 'code' in detail ? detail.code : null
  const messages: Record<string, string> = {
    spool_archived: 'spoolArchived', spool_not_found: 'spoolMissing',
    spool_unavailable: 'spoolUnavailable', print_not_planned: 'notPlanned', print_not_found: 'printMissing',
  }
  if (typeof code === 'string' && messages[code]) {
    if (detail && typeof detail === 'object' && 'spool_id' in detail) {
      const row = rows.find(row => Number(row.spoolId) === detail.spool_id)
      if (row) fieldErrors[`spools.${row.key}.spool_id`] = t(`prints.form.${messages[code]}`)
    }
    return result(messages[code])
  }
  if (error.status === 409) return result('conflictError')
  if (error.status === 404) return result('resourceMissing')
  if (error.status === 400 || error.status === 422) return result('validationError')
  return result('unexpectedError')
}
