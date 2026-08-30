import type { Material, Spool } from '../types/spool'

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

const gramsFormatter = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 2,
})

export function formatWeight(weightG: number): string {
  if (weightG >= 1000) return `${(weightG / 1000).toFixed(2)} kg`
  return `${gramsFormatter.format(weightG)} g`
}

export function formatPercent(percent: number): string {
  return `${new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(percent)}%`
}

export function formatCurrency(value: number | string, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(Number(value))
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value))
}
