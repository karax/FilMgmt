export type AnalyticsRangePreset =
  | 'last_7_days'
  | 'last_30_days'
  | 'last_90_days'
  | 'this_year'
  | 'last_12_months'
  | 'all_time'
  | 'custom'

export type AnalyticsBucket = 'day' | 'week' | 'month'

export interface AnalyticsFilters {
  range: AnalyticsRangePreset
  from?: string
  to?: string
  timezone: string
  material?: string
  brand?: string
  store?: string
  spoolId?: number
}

export interface AnalyticsPeriod {
  preset: AnalyticsRangePreset
  from: string | null
  to: string
  timezone: string
  date_field: string
}

export interface MoneyAmount {
  currency: string
  amount: string
}

export interface SpoolConsumptionRank {
  spool_id: number
  code: string
  display_name: string
  brand: string
  material: string
  color: string
  consumption_g: string
  print_count: number
}

export interface DimensionConsumption {
  name: string
  consumption_g: string
  print_count: number
}

export interface StoreSpend {
  store: string
  currency: string
  amount: string
  priced_spool_count: number
}

export interface StoreSpoolCount {
  store: string
  spool_count: number
}

export interface AnalyticsDashboard {
  period: AnalyticsPeriod
  consumption: {
    confirmed_g: string
    confirmed_kg: string
    estimated_costs: MoneyAmount[]
    confirmed_g_with_known_cost: string
    cost_coverage_percentage: string | null
  }
  printing: {
    actual_printing_seconds: number
    actual_printing_hours: string
    jobs_with_actual_duration: number
    total_terminal_jobs: number
    duration_coverage_percentage: string | null
    completed: number
    failed: number
    cancelled: number
    unknown_terminal: number
    success_rate_percentage: string | null
  }
  inventory: {
    active_spool_count: number
    current_remaining_g: string
    empty_spool_count: number
    archived_spool_count: number
  }
  reconciliation: {
    pending_print_count: number
    pending_filament_usage_count: number
  }
  highlights: {
    most_used_spool: SpoolConsumptionRank | null
    most_consumed_material: DimensionConsumption | null
    most_consumed_brand: DimensionConsumption | null
    highest_spend_stores_by_currency: StoreSpend[]
    most_spools_store: StoreSpoolCount | null
  }
}

export interface ConsumptionSeries {
  period: AnalyticsPeriod
  bucket: AnalyticsBucket
  points: Array<{ period: string; consumption_g: string }>
  unbucketed_consumption_g: string
}

export interface InventoryByMaterial {
  material: string
  remaining_g: string
  spool_count: number
}

export interface PurchasesByStore {
  period: AnalyticsPeriod
  by_spend: StoreSpend[]
  by_spool_count: StoreSpoolCount[]
}

export interface PurchaseSpendSeries {
  period: AnalyticsPeriod
  bucket: AnalyticsBucket
  points: Array<{ period: string; currency: string; amount: string }>
  unbucketed_amounts: MoneyAmount[]
}

export interface PrintActivity {
  period: AnalyticsPeriod
  bucket: AnalyticsBucket
  outcomes: {
    completed: number
    failed: number
    cancelled: number
    unknown_terminal: number
    success_rate_percentage: string | null
  }
  activity: {
    actual_printing_seconds: number
    actual_printing_hours: string
    jobs_with_actual_duration: number
    total_terminal_jobs: number
    duration_coverage_percentage: string | null
  }
  printing_seconds_by_period: Array<{ period: string; count: number }>
  completed_prints_by_period: Array<{ period: string; count: number }>
}

export interface TopConsumingPrint {
  print_job_id: number
  name: string
  started_at: string | null
  consumption_g: string
}
