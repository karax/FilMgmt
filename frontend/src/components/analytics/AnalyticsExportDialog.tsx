import { Download, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { downloadAnalyticsCsv } from '../../api/analyticsExport'
import type { AnalyticsBucket, AnalyticsFilters } from '../../types/analytics'
import {
  analyticsExportDatasets,
  isAnalyticsExportDataset,
  rawExportDatasets,
  type ExportDataset,
  type ExportScope,
} from '../../types/analyticsExport'

interface AnalyticsExportDialogProps {
  bucket: AnalyticsBucket
  filters: AnalyticsFilters
  onClose: () => void
  onDownloaded: (filename: string) => void
}

export function AnalyticsExportDialog({ bucket, filters, onClose, onDownloaded }: AnalyticsExportDialogProps) {
  const { t } = useTranslation()
  const [dataset, setDataset] = useState<ExportDataset>('consumption_over_time')
  const [scope, setScope] = useState<ExportScope>('current')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(false)
  const analyticsDataset = isAnalyticsExportDataset(dataset)

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !pending) onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose, pending])

  async function exportCsv() {
    setPending(true)
    setError(false)
    try {
      const filename = await downloadAnalyticsCsv(
        dataset,
        filters,
        bucket,
        analyticsDataset ? 'current' : scope,
      )
      onDownloaded(filename)
    } catch {
      setError(true)
    } finally {
      setPending(false)
    }
  }

  function selectDataset(next: ExportDataset) {
    setDataset(next)
    setError(false)
    if (isAnalyticsExportDataset(next)) setScope('current')
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-black/55 p-3 sm:p-5" role="presentation">
      <div aria-describedby="analytics-export-description" aria-labelledby="analytics-export-title" aria-modal="true" className="my-4 flex max-h-[calc(100dvh-2rem)] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-2xl" role="dialog">
        <header className="flex items-start justify-between gap-5 border-b border-line px-5 py-4 sm:px-6">
          <div>
            <h2 className="text-lg font-semibold text-ink" id="analytics-export-title">{t('analytics.export.title')}</h2>
            <p className="mt-1 text-sm leading-5 text-ink-muted" id="analytics-export-description">{t('analytics.export.description')}</p>
          </div>
          <button aria-label={t('common.close')} className="grid size-9 shrink-0 place-items-center rounded-md border border-line text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" disabled={pending} onClick={onClose} type="button"><X aria-hidden="true" className="size-4" /></button>
        </header>

        <div className="overflow-y-auto px-5 py-5 sm:px-6">
          <DatasetGroup datasets={analyticsExportDatasets} selected={dataset} title={t('analytics.export.analyticsGroup')} onSelect={selectDataset} />
          <DatasetGroup className="mt-6" datasets={rawExportDatasets} selected={dataset} title={t('analytics.export.rawGroup')} onSelect={selectDataset} />

          <fieldset className="mt-6 rounded-lg border border-line bg-canvas/50 p-4">
            <legend className="px-1 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted">{t('analytics.export.scopeTitle')}</legend>
            {analyticsDataset ? (
              <div>
                <p className="text-sm font-semibold text-ink">{t('analytics.export.currentFilters')}</p>
                <p className="mt-1 text-xs leading-5 text-ink-muted">{t('analytics.export.analyticsScopeHelp')}</p>
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                <ScopeOption checked={scope === 'current'} description={t('analytics.export.currentScopeHelp')} label={t('analytics.export.currentFilters')} onChange={() => setScope('current')} />
                <ScopeOption checked={scope === 'all'} description={t('analytics.export.allScopeHelp')} label={t('analytics.export.allData')} onChange={() => setScope('all')} />
              </div>
            )}
            {dataset === 'spools' && scope === 'current' && <p className="mt-3 text-xs text-ink-muted">{t('analytics.export.inventorySnapshotHelp')}</p>}
          </fieldset>

          {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/[0.05] px-4 py-3 text-sm text-red-700 dark:text-red-300" role="alert"><strong>{t('analytics.export.errorTitle')}</strong>{' '}<span>{t('analytics.export.errorDescription')}</span></div>}
        </div>

        <footer className="flex flex-col-reverse gap-3 border-t border-line px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
          <button className="rounded-md border border-line px-4 py-2.5 text-sm font-semibold text-ink hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" disabled={pending} onClick={onClose} type="button">{t('common.cancel')}</button>
          <button className="inline-flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-white disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" disabled={pending} onClick={() => void exportCsv()} type="button"><Download aria-hidden="true" className="size-4" />{pending ? t('analytics.export.preparing') : t('analytics.export.download')}</button>
        </footer>
      </div>
    </div>
  )
}

function DatasetGroup({ datasets, selected, title, onSelect, className = '' }: { datasets: readonly ExportDataset[]; selected: ExportDataset; title: string; onSelect: (dataset: ExportDataset) => void; className?: string }) {
  const { t } = useTranslation()
  return (
    <fieldset className={className}>
      <legend className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-muted">{title}</legend>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {datasets.map((item, index) => (
          <label className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-3 text-sm transition-colors ${selected === item ? 'border-accent bg-accent-soft' : 'border-line hover:border-accent/60'}`} key={item}>
            <input autoFocus={index === 0 && datasets === analyticsExportDatasets} checked={selected === item} className="mt-0.5 accent-[var(--color-accent)]" name="analytics-export-dataset" onChange={() => onSelect(item)} type="radio" value={item} />
            <span className="font-medium text-ink">{t(`analytics.export.datasets.${item}`)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function ScopeOption({ checked, label, description, onChange }: { checked: boolean; label: string; description: string; onChange: () => void }) {
  return <label className={`flex cursor-pointer gap-3 rounded-lg border p-3 ${checked ? 'border-accent bg-accent-soft' : 'border-line bg-surface'}`}><input checked={checked} className="mt-1 accent-[var(--color-accent)]" name="analytics-export-scope" onChange={onChange} type="radio" /><span><span className="block text-sm font-semibold text-ink">{label}</span><span className="mt-1 block text-xs leading-5 text-ink-muted">{description}</span></span></label>
}
