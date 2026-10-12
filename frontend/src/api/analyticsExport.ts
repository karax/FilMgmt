import type { AnalyticsBucket, AnalyticsFilters } from '../types/analytics'
import type { ExportDataset, ExportScope } from '../types/analyticsExport'
import { analyticsQueryParams } from './analytics'
import { API_BASE_URL, ApiError } from './client'

function exportFilename(disposition: string | null): string {
  const match = disposition?.match(/filename="([a-zA-Z0-9._-]+)"/)
  return match?.[1] ?? 'analytics-export.csv'
}

export async function downloadAnalyticsCsv(
  dataset: ExportDataset,
  filters: AnalyticsFilters,
  bucket: AnalyticsBucket,
  scope: ExportScope,
): Promise<string> {
  const params = analyticsQueryParams(filters, { dataset, bucket, scope })
  const response = await fetch(`${API_BASE_URL}/api/analytics/export?${params}`, {
    headers: { Accept: 'text/csv' },
    method: 'GET',
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new ApiError('CSV export failed.', response.status, detail)
  }

  const filename = exportFilename(response.headers.get('Content-Disposition'))
  const objectUrl = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.download = filename
  anchor.href = objectUrl
  anchor.click()
  URL.revokeObjectURL(objectUrl)
  return filename
}
