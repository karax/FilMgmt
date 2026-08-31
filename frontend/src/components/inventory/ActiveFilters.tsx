import type { SpoolFilters } from '../../types/spool'
import { useTranslation } from 'react-i18next'

export function ActiveFilters({ filters, labels, onRemove }: { filters: SpoolFilters; labels: Partial<Record<keyof SpoolFilters, string>>; onRemove: (key: keyof SpoolFilters) => void }) {
  const { t } = useTranslation()
  const entries = (Object.keys(filters) as (keyof SpoolFilters)[]).filter((key) => filters[key] !== undefined)
  if (!entries.length) return null
  return <div className="mb-4 flex flex-wrap items-center gap-2" aria-label={t('inventory.activeFilters')}><span className="text-sm text-ink-muted">{t('inventory.activeFilters')}</span>{entries.map((key) => <button className="inline-flex items-center gap-1 rounded-full border border-line bg-surface-raised px-2.5 py-1 text-xs font-semibold text-ink hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" key={key} onClick={() => onRemove(key)} type="button">{labels[key] ?? key}<span aria-hidden="true">×</span><span className="sr-only">{t('inventory.removeFilter', { filter: labels[key] ?? key })}</span></button>)}</div>
}
