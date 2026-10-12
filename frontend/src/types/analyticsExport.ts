export type AnalyticsExportDataset =
  | 'consumption_over_time'
  | 'top_spools'
  | 'consumption_by_material'
  | 'consumption_by_brand'
  | 'inventory_by_material'
  | 'purchases_by_store'
  | 'purchase_spend_over_time'
  | 'print_outcomes'
  | 'print_activity'
  | 'largest_consuming_prints'

export type RawExportDataset =
  | 'spools'
  | 'prints'
  | 'filament_usage'
  | 'confirmed_consumption'
  | 'purchases'
  | 'ledger'
  | 'calibrations'

export type ExportDataset = AnalyticsExportDataset | RawExportDataset
export type ExportScope = 'current' | 'all'

export const analyticsExportDatasets: readonly AnalyticsExportDataset[] = [
  'consumption_over_time',
  'top_spools',
  'consumption_by_material',
  'consumption_by_brand',
  'inventory_by_material',
  'purchases_by_store',
  'purchase_spend_over_time',
  'print_outcomes',
  'print_activity',
  'largest_consuming_prints',
]

export const rawExportDatasets: readonly RawExportDataset[] = [
  'spools',
  'prints',
  'filament_usage',
  'confirmed_consumption',
  'purchases',
  'ledger',
  'calibrations',
]

export function isAnalyticsExportDataset(dataset: ExportDataset): dataset is AnalyticsExportDataset {
  return analyticsExportDatasets.includes(dataset as AnalyticsExportDataset)
}
