import type { AnalyticsBucket, AnalyticsRangePreset } from '../types/analytics'

export function asNumber(value: number | string | null | undefined): number {
  if (value === null || value === undefined) return 0
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export function formatGrams(value: number | string, locale = 'en'): string {
  const grams = asNumber(value)
  if (Math.abs(grams) >= 1000) {
    return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(grams / 1000)} kg`
  }
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(grams)} g`
}

export function formatCurrency(value: number | string, currency: string, locale = 'en'): string {
  try {
    return new Intl.NumberFormat(locale, { style: 'currency', currency }).format(asNumber(value))
  } catch {
    return `${currency} ${new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(asNumber(value))}`
  }
}

export function formatPercentage(value: number | string | null, locale = 'en'): string {
  if (value === null) return '—'
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(asNumber(value))}%`
}

export function formatDuration(seconds: number, locale = 'en'): string {
  const minutes = Math.max(0, Math.round(seconds / 60))
  const hours = Math.floor(minutes / 60)
  const remainder = minutes % 60
  if (hours === 0) return `${remainder}m`
  if (remainder === 0) return `${new Intl.NumberFormat(locale).format(hours)}h`
  return `${new Intl.NumberFormat(locale).format(hours)}h ${remainder}m`
}

export function bucketForRange(range: AnalyticsRangePreset): AnalyticsBucket {
  if (range === 'last_7_days' || range === 'last_30_days' || range === 'custom') return 'day'
  if (range === 'last_90_days' || range === 'this_year') return 'week'
  return 'month'
}

export function formatPeriodLabel(period: string, bucket: AnalyticsBucket, locale = 'en'): string {
  const date = new Date(`${period.length === 7 ? `${period}-01` : period}T00:00:00Z`)
  if (Number.isNaN(date.valueOf())) return period
  if (bucket === 'month') return new Intl.DateTimeFormat(locale, { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date)
  return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(date)
}

export function analyticsTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
}
