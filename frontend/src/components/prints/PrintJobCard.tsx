import { useTranslation } from 'react-i18next'
import { Link, useInRouterContext } from 'react-router-dom'

import { useElapsedMinutes } from '../../hooks/useElapsedMinutes'
import { formatCurrency, formatWeight } from '../../lib/inventory'
import { formatDuration, formatPrintDateTime } from '../../lib/printJobs'
import type { PrintJob } from '../../types/printJob'
import type { Spool } from '../../types/spool'
import { PrintJobStatusBadge } from './PrintJobStatusBadge'
import { filamentColor, PrintJobThumbnail } from './PrintJobThumbnail'

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs font-medium text-ink-muted">{label}</dt><dd className="mt-1 text-sm font-semibold text-ink">{value}</dd></div>
}

type PrintJobCardProps = {
  printJob: PrintJob
  spools: Spool[]
  onStart?: (printJob: PrintJob) => void
  onFinish?: (printJob: PrintJob) => void
}

function RunningElapsed({ startedAt }: { startedAt: string | null }) {
  const { t } = useTranslation()
  const minutes = useElapsedMinutes(startedAt)
  return <p className="mt-4 text-sm font-semibold text-amber-800 dark:text-amber-200">{minutes == null ? t('prints.running.unavailable') : t('prints.running.elapsed', { duration: formatDuration(minutes) })}</p>
}

function materialCostValue(printJob: PrintJob): string | null {
  const totals = new Map<string, number>()
  for (const link of printJob.spools) {
    if (link.material_cost == null || !link.material_cost_currency) continue
    totals.set(link.material_cost_currency, (totals.get(link.material_cost_currency) ?? 0) + Number(link.material_cost))
  }
  if (!totals.size) return null
  return [...totals.entries()].map(([currency, value]) => formatCurrency(value, currency)).join(' · ')
}

export function PrintJobCard({ printJob, spools, onStart, onFinish }: PrintJobCardProps) {
  const { t } = useTranslation()
  const isPrinterManaged = Boolean(printJob.capture_mode)
  const isCompleted = printJob.status === 'SUCCESS' || printJob.status === 'COMPLETED'
  const isActive = printJob.status === 'PRINTING' || printJob.status === 'PAUSED'
  const weight = isCompleted ? printJob.total_actual_weight_g : printJob.total_estimated_weight_g
  const duration = isCompleted ? (printJob.actual_time_minutes ?? (printJob.duration_seconds == null ? null : Math.floor(printJob.duration_seconds / 60))) : printJob.estimated_time_minutes
  const spoolName = spools.slice(0, 3).map((spool) => `${spool.display_name ?? spool.code} · ${spool.code}`).join(' · ') || t('prints.spoolFallback', { id: '?' })
  const amsSummary = printJob.ams_snapshot?.ams_units?.flatMap((unit) => unit.trays ?? []).map((tray) => [tray.material_type, tray.color ? `#${tray.color.slice(0, 6)}` : null].filter(Boolean).join(' ')).filter(Boolean).join(' · ')
  const materialSummary = isPrinterManaged ? (amsSummary || t('prints.amsUnavailable')) : spoolName
  const title = printJob.name ?? printJob.gcode_file?.split('/').pop() ?? t('prints.unnamed', { id: printJob.id })
  const date = isActive ? printJob.started_at : printJob.finished_at
  const dateLabel = isActive ? t('prints.fields.started') : t('prints.fields.finished')
  const filaments = printJob.filaments ?? []

  return (
    <article className="rounded-lg border border-line bg-surface p-5 shadow-sm">
      <div className="flex gap-4">
        {isPrinterManaged && <PrintJobThumbnail alt={title} className="size-24 sm:size-28" url={printJob.thumbnail_url} />}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0"><h3 className="break-words text-base font-semibold text-ink">{title}</h3><p className="mt-1 text-sm text-ink-muted">{filaments.length ? t('prints.metadata.filamentCount', { count: filaments.length }) : materialSummary}{!isPrinterManaged && printJob.spools.length > 3 ? ` · ${t('prints.spoolsMore', { count: printJob.spools.length - 3 })}` : ''}</p>{isPrinterManaged ? <p className="font-mono text-xs text-ink-muted">{printJob.printer_serial}</p> : <p className="font-mono text-xs text-ink-muted">{t(printJob.status === 'PRINTING' ? 'prints.spoolsInUse' : 'prints.spoolCount', { count: printJob.spools.length })}</p>}</div>
            <PrintJobStatusBadge status={printJob.status} />
          </div>
          {filaments.length > 0 && <ul className="mt-3 space-y-1.5 text-xs text-ink-muted">{filaments.slice(0, 3).map((filament) => <li className="flex items-center justify-between gap-3" key={filament.id}><span className="flex min-w-0 items-center gap-2"><span aria-hidden="true" className="size-3 shrink-0 rounded-full border border-black/10" style={{ backgroundColor: filamentColor(filament.color) ?? 'transparent' }} /><span className="truncate">{filament.material_type ?? t('prints.metadata.unknownMaterial')}</span></span><strong className="shrink-0 text-ink">{filament.used_g == null ? '—' : `${Number(filament.used_g).toFixed(1)} g`}</strong></li>)}</ul>}
        </div>
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-x-5 gap-y-4">
        {(printJob.printer_name || printJob.printer_serial) && <Detail label={t('prints.fields.printer')} value={printJob.printer_name ?? printJob.printer_serial!} />}
        {printJob.final_progress != null && <Detail label={t('prints.fields.progress')} value={`${printJob.final_progress}%`} />}
        {weight != null && <Detail label={isCompleted ? t('prints.fields.actualWeight') : t('prints.fields.estimatedWeight')} value={formatWeight(Number(weight))} />}
        {duration != null && <Detail label={isCompleted ? t('prints.fields.actualTime') : t('prints.fields.estimatedTime')} value={formatDuration(duration)} />}
        {date && <Detail label={dateLabel} value={formatPrintDateTime(date)} />}
        {isPrinterManaged && printJob.estimated_filament_g != null && <Detail label={t('prints.metadata.estimatedTotal')} value={formatWeight(Number(printJob.estimated_filament_g))} />}
        {isCompleted && materialCostValue(printJob) && <Detail label={t('prints.fields.cost')} value={materialCostValue(printJob)!} />}
      </dl>
      {isPrinterManaged && printJob.enrichment_status && printJob.enrichment_status !== 'ENRICHED' && <p className="mt-4 rounded-md bg-surface-raised px-3 py-2 text-xs text-ink-muted">{t(`prints.metadata.status.${printJob.enrichment_status}`)}</p>}
      {printJob.status === 'PRINTING' && <RunningElapsed startedAt={printJob.started_at} />}
      {isCompleted && printJob.spools.some((link) => link.actual_weight_g != null) && <ul className="mt-4 space-y-1 text-xs text-ink-muted">{printJob.spools.filter((link) => link.actual_weight_g != null).map((link) => { const spool = spools.find((item) => item.id === link.spool_id); return <li key={link.spool_id}>{spool?.display_name ?? spool?.code ?? t('prints.spoolFallback', { id: link.spool_id })}: <strong className="text-ink">{formatWeight(Number(link.actual_weight_g))}</strong></li> })}</ul>}
      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-end">
        {printJob.status === 'PLANNED' && <><EditLink id={printJob.id} label={t('prints.actions.edit')} /><button className="rounded-md bg-accent px-3 py-2 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onClick={() => onStart?.(printJob)} type="button">{t('prints.actions.start')}</button></>}
        {printJob.status === 'PRINTING' && !isPrinterManaged && <button className="rounded-md bg-accent px-3 py-2 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onClick={() => onFinish?.(printJob)} type="button">{t('prints.actions.finish')}</button>}
        <DetailsLink id={printJob.id} label={t('prints.actions.details')} />
      </div>
    </article>
  )
}

function DetailsLink({ id, label }: { id: number; label: string }) {
  const inRouter = useInRouterContext()
  const className = 'rounded-md border border-line px-3 py-2 text-center text-sm font-bold text-ink hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent'
  const destination = `/prints/${id}`
  return inRouter ? <Link className={className} to={destination}>{label}</Link> : <a className={className} href={destination}>{label}</a>
}

function EditLink({ id, label }: { id: number; label: string }) {
  const inRouter = useInRouterContext()
  const className = 'rounded-md border border-line px-3 py-2 text-center text-sm font-bold text-ink hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent'
  const destination = `/prints/${id}/edit`
  return inRouter ? <Link className={className} to={destination}>{label}</Link> : <a className={className} href={destination}>{label}</a>
}
