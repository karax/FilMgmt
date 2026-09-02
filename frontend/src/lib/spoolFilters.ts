import type { SpoolFilters, SpoolStatus } from '../types/spool'

const statuses: readonly SpoolStatus[] = ['SEALED', 'OPEN', 'IN_USE', 'LOW', 'EMPTY', 'NEEDS_DRYING', 'ARCHIVED']
export const spoolStatuses = statuses

function numberParam(params: URLSearchParams, name: string, range?: [number, number]) {
  const value = Number(params.get(name))
  if (!params.has(name) || !Number.isFinite(value) || (range && (value < range[0] || value > range[1]))) return undefined
  return value
}

export function filtersFromSearchParams(params: URLSearchParams): SpoolFilters {
  const status = params.get('status')
  const bool = (name: string) => params.get(name) === 'true' ? true : params.get(name) === 'false' ? false : undefined
  return {
    search: params.get('search')?.trim() || undefined,
    manufacturerId: numberParam(params, 'manufacturer_id', [0, Number.MAX_SAFE_INTEGER]),
    materialId: numberParam(params, 'material_id', [0, Number.MAX_SAFE_INTEGER]),
    status: statuses.includes(status as SpoolStatus) ? status as SpoolStatus : undefined,
    needsDrying: bool('needs_drying'),
    minWeightG: numberParam(params, 'min_weight_g', [0, Number.MAX_SAFE_INTEGER]),
    maxWeightG: numberParam(params, 'max_weight_g', [0, Number.MAX_SAFE_INTEGER]),
    minRemainingPercent: numberParam(params, 'min_remaining_percent', [0, 100]),
    maxRemainingPercent: numberParam(params, 'max_remaining_percent', [0, 100]),
    includeArchived: bool('include_archived') === true ? true : undefined,
  }
}

export function filtersToSearchParams(filters: SpoolFilters): URLSearchParams {
  const params = new URLSearchParams()
  const entries: [string, number | string | boolean | undefined][] = [
    ['search', filters.search?.trim() || undefined],
    ['manufacturer_id', filters.manufacturerId], ['material_id', filters.materialId], ['status', filters.status], ['needs_drying', filters.needsDrying], ['min_weight_g', filters.minWeightG], ['max_weight_g', filters.maxWeightG], ['min_remaining_percent', filters.minRemainingPercent], ['max_remaining_percent', filters.maxRemainingPercent], ['include_archived', filters.includeArchived],
  ]
  for (const [name, value] of entries) if (value !== undefined) params.set(name, String(value))
  return params
}

export function activeFilterCount(filters: SpoolFilters) { return Object.values(filters).filter((value) => value !== undefined).length }
