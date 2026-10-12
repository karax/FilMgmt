import type {
  AnalyticsBucket,
  AnalyticsDashboard,
  AnalyticsFilters,
  ConsumptionSeries,
  DimensionConsumption,
  InventoryByMaterial,
  PrintActivity,
  PurchaseSpendSeries,
  PurchasesByStore,
  SpoolConsumptionRank,
  TopConsumingPrint,
} from '../types/analytics'
import { apiGet } from './client'

export function analyticsQueryParams(
  filters: AnalyticsFilters,
  extra: Record<string, number | string | undefined> = {},
): URLSearchParams {
  const params = new URLSearchParams({ range: filters.range, timezone: filters.timezone })
  if (filters.range === 'custom' && filters.from && filters.to) {
    params.set('from', filters.from)
    params.set('to', filters.to)
  }
  for (const [key, value] of Object.entries(extra)) {
    if (value !== undefined) params.set(key, String(value))
  }
  if (filters.material) params.set('material', filters.material)
  if (filters.brand) params.set('brand', filters.brand)
  if (filters.store) params.set('store', filters.store)
  if (filters.spoolId !== undefined) params.set('spool_id', String(filters.spoolId))
  return params
}

function analyticsGet<T>(
  path: string,
  filters: AnalyticsFilters,
  signal?: AbortSignal,
  extra?: Record<string, number | string | undefined>,
): Promise<T> {
  return apiGet<T>(`/api/analytics/${path}?${analyticsQueryParams(filters, extra)}`, signal)
}

export const getAnalyticsDashboard = (filters: AnalyticsFilters, signal?: AbortSignal) =>
  analyticsGet<AnalyticsDashboard>('dashboard', filters, signal)

export const getConsumptionSeries = (filters: AnalyticsFilters, bucket: AnalyticsBucket, signal?: AbortSignal) =>
  analyticsGet<ConsumptionSeries>('consumption-over-time', filters, signal, { bucket })

export const getTopSpools = (filters: AnalyticsFilters, signal?: AbortSignal) =>
  analyticsGet<SpoolConsumptionRank[]>('top-spools', filters, signal, { limit: 10 })

export const getConsumptionByMaterial = (filters: AnalyticsFilters, signal?: AbortSignal) =>
  analyticsGet<DimensionConsumption[]>('consumption-by-material', filters, signal)

export const getConsumptionByBrand = (filters: AnalyticsFilters, signal?: AbortSignal) =>
  analyticsGet<DimensionConsumption[]>('consumption-by-brand', filters, signal)

export const getInventoryByMaterial = (filters: AnalyticsFilters, signal?: AbortSignal) =>
  analyticsGet<InventoryByMaterial[]>('inventory-by-material', filters, signal)

export const getPurchasesByStore = (filters: AnalyticsFilters, signal?: AbortSignal) =>
  analyticsGet<PurchasesByStore>('purchases-by-store', filters, signal, { limit: 10 })

export const getPurchaseSpendSeries = (filters: AnalyticsFilters, bucket: AnalyticsBucket, signal?: AbortSignal) =>
  analyticsGet<PurchaseSpendSeries>('purchase-spend-over-time', filters, signal, { bucket })

export const getPrintActivity = (filters: AnalyticsFilters, bucket: AnalyticsBucket, signal?: AbortSignal) =>
  analyticsGet<PrintActivity>('print-activity', filters, signal, { bucket })

export const getTopConsumingPrints = (filters: AnalyticsFilters, signal?: AbortSignal) =>
  analyticsGet<TopConsumingPrint[]>('top-consuming-prints', filters, signal, { limit: 5 })
