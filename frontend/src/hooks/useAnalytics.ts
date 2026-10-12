import { useQuery } from '@tanstack/react-query'

import {
  getAnalyticsDashboard,
  getConsumptionByBrand,
  getConsumptionByMaterial,
  getConsumptionSeries,
  getInventoryByMaterial,
  getPrintActivity,
  getPurchaseSpendSeries,
  getPurchasesByStore,
  getTopConsumingPrints,
  getTopSpools,
} from '../api/analytics'
import type { AnalyticsBucket, AnalyticsFilters } from '../types/analytics'

export const analyticsQueryKey = ['analytics'] as const

function options(filters: AnalyticsFilters) {
  return { staleTime: 60_000, enabled: filters.range !== 'custom' || Boolean(filters.from && filters.to) }
}

export function useAnalyticsDashboard(filters: AnalyticsFilters) {
  return useQuery({ queryKey: [...analyticsQueryKey, 'dashboard', filters], queryFn: ({ signal }) => getAnalyticsDashboard(filters, signal), ...options(filters) })
}

export function useConsumptionSeries(filters: AnalyticsFilters, bucket: AnalyticsBucket) {
  return useQuery({ queryKey: [...analyticsQueryKey, 'consumption-series', filters, bucket], queryFn: ({ signal }) => getConsumptionSeries(filters, bucket, signal), ...options(filters) })
}

export function useTopSpools(filters: AnalyticsFilters) {
  return useQuery({ queryKey: [...analyticsQueryKey, 'top-spools', filters], queryFn: ({ signal }) => getTopSpools(filters, signal), ...options(filters) })
}

export function useConsumptionByMaterial(filters: AnalyticsFilters) {
  return useQuery({ queryKey: [...analyticsQueryKey, 'consumption-material', filters], queryFn: ({ signal }) => getConsumptionByMaterial(filters, signal), ...options(filters) })
}

export function useConsumptionByBrand(filters: AnalyticsFilters) {
  return useQuery({ queryKey: [...analyticsQueryKey, 'consumption-brand', filters], queryFn: ({ signal }) => getConsumptionByBrand(filters, signal), ...options(filters) })
}

export function useInventoryByMaterial(filters: AnalyticsFilters) {
  return useQuery({ queryKey: [...analyticsQueryKey, 'inventory-material', filters], queryFn: ({ signal }) => getInventoryByMaterial(filters, signal), ...options(filters) })
}

export function usePurchasesByStore(filters: AnalyticsFilters) {
  return useQuery({ queryKey: [...analyticsQueryKey, 'purchases-store', filters], queryFn: ({ signal }) => getPurchasesByStore(filters, signal), ...options(filters) })
}

export function usePurchaseSpendSeries(filters: AnalyticsFilters, bucket: AnalyticsBucket) {
  return useQuery({ queryKey: [...analyticsQueryKey, 'purchase-series', filters, bucket], queryFn: ({ signal }) => getPurchaseSpendSeries(filters, bucket, signal), ...options(filters) })
}

export function usePrintActivity(filters: AnalyticsFilters, bucket: AnalyticsBucket) {
  return useQuery({ queryKey: [...analyticsQueryKey, 'print-activity', filters, bucket], queryFn: ({ signal }) => getPrintActivity(filters, bucket, signal), ...options(filters) })
}

export function useTopConsumingPrints(filters: AnalyticsFilters) {
  return useQuery({ queryKey: [...analyticsQueryKey, 'top-prints', filters], queryFn: ({ signal }) => getTopConsumingPrints(filters, signal), ...options(filters) })
}
