import type { Material, Spool } from '../types/spool'
import i18n from '../i18n'

export interface InventorySummary {
  totalSpools: number
  totalWeightG: number
  lowCount: number
  emptyCount: number
  needsDryingCount: number
}

export interface MaterialGroup {
  material: Material
  spoolCount: number
  totalWeightG: number
}

function numericValue(value: number | string): number {
  return Number(value)
}

export function calculateInventorySummary(
  spools: readonly Spool[],
): InventorySummary {
  return spools.reduce<InventorySummary>(
    (summary, spool) => ({
      totalSpools: summary.totalSpools + 1,
      totalWeightG:
        summary.totalWeightG + numericValue(spool.current_filament_weight_g),
      lowCount: summary.lowCount + Number(spool.status === 'LOW'),
      emptyCount: summary.emptyCount + Number(spool.status === 'EMPTY'),
      needsDryingCount:
        summary.needsDryingCount + Number(spool.needs_drying),
    }),
    {
      totalSpools: 0,
      totalWeightG: 0,
      lowCount: 0,
      emptyCount: 0,
      needsDryingCount: 0,
    },
  )
}

export function groupSpoolsByMaterial(
  spools: readonly Spool[],
): MaterialGroup[] {
  const groups = new Map<number, MaterialGroup>()

  for (const spool of spools) {
    const existing = groups.get(spool.material.id)
    const weight = numericValue(spool.current_filament_weight_g)

    if (existing) {
      existing.spoolCount += 1
      existing.totalWeightG += weight
    } else {
      groups.set(spool.material.id, {
        material: spool.material,
        spoolCount: 1,
        totalWeightG: weight,
      })
    }
  }

  return [...groups.values()].sort(
    (left, right) =>
      right.spoolCount - left.spoolCount ||
      left.material.name.localeCompare(right.material.name),
  )
}

function criticalRank(spool: Spool): number {
  if (spool.status === 'EMPTY') return 0
  if (spool.status === 'LOW') return 1
  return 2
}

export function sortCriticalSpools(spools: readonly Spool[]): Spool[] {
  return [...spools]
    .filter(
      (spool) =>
        spool.status === 'EMPTY' ||
        spool.status === 'LOW' ||
        spool.needs_drying,
    )
    .sort(
      (left, right) =>
        criticalRank(left) - criticalRank(right) ||
        left.remaining_percent - right.remaining_percent ||
        left.code.localeCompare(right.code),
    )
}

function locale(): string { return i18n.language === 'en' ? 'en-US' : 'pt-BR' }

export function formatWeight(weightG: number): string {
  if (weightG >= 1000) return `${new Intl.NumberFormat(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(weightG / 1000)} kg`
  return `${new Intl.NumberFormat(locale(), { maximumFractionDigits: 2 }).format(weightG)} g`
}

export function formatPercent(percent: number): string {
  return `${new Intl.NumberFormat(locale(), {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(percent)}%`
}

export function formatCurrency(value: number | string, currency: string): string {
  return new Intl.NumberFormat(locale(), {
    style: 'currency',
    currency,
  }).format(Number(value))
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat(locale(), i18n.language === 'en' ? { month: 'short', day: 'numeric', year: 'numeric' } : { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value))
}
