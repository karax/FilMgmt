import { useTranslation } from 'react-i18next'
import { Link, useInRouterContext } from 'react-router-dom'

import { useElapsedMinutes } from '../../hooks/useElapsedMinutes'
import { formatCurrency, formatWeight } from '../../lib/inventory'
import { formatDuration, formatPrintDateTime } from '../../lib/printJobs'
import type { PrintJob } from '../../types/printJob'
import type { Spool } from '../../types/spool'
import { PrintJobStatusBadge } from './PrintJobStatusBadge'

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
  const isCompleted = printJob.status === 'SUCCESS'
  const weight = isCompleted ? printJob.total_actual_weight_g : printJob.total_estimated_weight_g
  const duration = isCompleted ? printJob.actual_time_minutes : printJob.estimated_time_minutes
  const spoolName = spools.slice(0, 3).map((spool) => `${spool.display_name ?? spool.code} · ${spool.code}`).join(' · ') || t('prints.spoolFallback', { id: '?' })
  const date = printJob.status === 'PRINTING' ? printJob.started_at : isCompleted ? printJob.finished_at : null
  const dateLabel = printJob.status === 'PRINTING' ? t('prints.fields.started') : t('prints.fields.finished')

  return (
    <article className="rounded-lg border border-line bg-surface p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0"><h3 className="break-words text-base font-semibold text-ink">{printJob.name}</h3><p className="mt-1 text-sm text-ink-muted">{spoolName}{printJob.spools.length > 3 ? ` · ${t('prints.spoolsMore', { count: printJob.spools.length - 3 })}` : ''}</p><p className="font-mono text-xs text-ink-muted">{t(printJob.status === 'PRINTING' ? 'prints.spoolsInUse' : 'prints.spoolCount', { count: printJob.spools.length })}</p></div>
        <PrintJobStatusBadge status={printJob.status} />
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-x-5 gap-y-4">
        {printJob.printer_name && <Detail label={t('prints.fields.printer')} value={printJob.printer_name} />}
        {weight != null && <Detail label={isCompleted ? t('prints.fields.actualWeight') : t('prints.fields.estimatedWeight')} value={formatWeight(Number(weight))} />}
        {duration != null && <Detail label={isCompleted ? t('prints.fields.actualTime') : t('prints.fields.estimatedTime')} value={formatDuration(duration)} />}
        {date && <Detail label={dateLabel} value={formatPrintDateTime(date)} />}
        {isCompleted && materialCostValue(printJob) && <Detail label={t('prints.fields.cost')} value={materialCostValue(printJob)!} />}
      </dl>
      {printJob.status === 'PRINTING' && <RunningElapsed startedAt={printJob.started_at} />}
      {isCompleted && printJob.spools.some((link) => link.actual_weight_g != null) && <ul className="mt-4 space-y-1 text-xs text-ink-muted">{printJob.spools.filter((link) => link.actual_weight_g != null).map((link) => { const spool = spools.find((item) => item.id === link.spool_id); return <li key={link.spool_id}>{spool?.display_name ?? spool?.code ?? t('prints.spoolFallback', { id: link.spool_id })}: <strong className="text-ink">{formatWeight(Number(link.actual_weight_g))}</strong></li> })}</ul>}
      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-end">
        {printJob.status === 'PLANNED' && <><EditLink id={printJob.id} label={t('prints.actions.edit')} /><button className="rounded-md bg-accent px-3 py-2 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onClick={() => onStart?.(printJob)} type="button">{t('prints.actions.start')}</button></>}
        {printJob.status === 'PRINTING' && <button className="rounded-md bg-accent px-3 py-2 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onClick={() => onFinish?.(printJob)} type="button">{t('prints.actions.finish')}</button>}
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
