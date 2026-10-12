import { AlertCircle, ArrowLeft, Boxes, CalendarClock, CircleDollarSign, Layers3, Pencil, RefreshCw, StickyNote } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { isApiError } from '../api/client'
import { FinishPrintDialog, StartPrintDialog, type ResolvedPrintJobSpool } from '../components/prints/PrintLifecycleDialogs'
import { PrintJobStatusBadge } from '../components/prints/PrintJobStatusBadge'
import { filamentColor, PrintJobThumbnail } from '../components/prints/PrintJobThumbnail'
import { SpoolStatusBadge } from '../components/spool/SpoolStatusBadge'
import { useElapsedMinutes } from '../hooks/useElapsedMinutes'
import { usePrintJob, useRequestPrintJobEnrichment } from '../hooks/usePrintJob'
import { useSpools } from '../hooks/useSpools'
import { formatCurrency, formatWeight } from '../lib/inventory'
import { formatDuration, formatPrintDateTime } from '../lib/printJobs'
import type { PrintJob, PrintJobSpool } from '../types/printJob'
import type { Spool } from '../types/spool'

type PrintAction = 'start' | 'finish' | null

export function PrintJobDetailsPage() {
  const { t } = useTranslation()
  const { id } = useParams()
  const numericId = id && /^\d+$/.test(id) && Number(id) > 0 ? Number(id) : undefined
  const printQuery = usePrintJob(numericId)
  const enrichmentMutation = useRequestPrintJobEnrichment(numericId ?? 0)
  const spoolsQuery = useSpools({ includeArchived: true })
  const [action, setAction] = useState<PrintAction>(null)
  const [feedback, setFeedback] = useState<string | null>(null)

  const spoolMap = useMemo(() => new Map((spoolsQuery.data ?? []).map((spool) => [spool.id, spool])), [spoolsQuery.data])
  const entries = useMemo<ResolvedPrintJobSpool[]>(() => printQuery.data?.spools.map((link) => ({ link, spool: spoolMap.get(link.spool_id) })) ?? [], [printQuery.data, spoolMap])

  useEffect(() => {
    if (!action || !printQuery.data) return
    const expected = action === 'start' ? 'PLANNED' : 'PRINTING'
    if (printQuery.data.status !== expected) setAction(null)
  }, [action, printQuery.data])

  if (!numericId) return <PrintNotFound />
  if (printQuery.error && isApiError(printQuery.error) && printQuery.error.status === 404) return <PrintNotFound />
  if (printQuery.error || spoolsQuery.error) return <PrintLoadError isFetching={printQuery.isFetching || spoolsQuery.isFetching} onRetry={() => void Promise.all([printQuery.refetch(), spoolsQuery.refetch()])} />
  if (printQuery.isPending || spoolsQuery.isPending) return <PrintDetailsSkeleton />
  if (!printQuery.data) return <PrintNotFound />

  const printJob = printQuery.data
  return (
    <main aria-labelledby="print-details-title">
      <Link className="inline-flex items-center gap-2 text-sm font-semibold text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" to="/prints"><ArrowLeft aria-hidden="true" className="size-4" />{t('prints.details.back')}</Link>
      <header className="mt-5 flex flex-col gap-5 border-b border-line pb-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.16em] text-ink-muted">{t('prints.details.identifier', { id: printJob.id })}</p>
          <h1 className="mt-2 break-words text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl" id="print-details-title">{printJob.name ?? printJob.gcode_file?.split('/').pop() ?? t('prints.unnamed', { id: printJob.id })}</h1>
          <div className="mt-3"><PrintJobStatusBadge status={printJob.status} /></div>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-end">
          {printJob.status === 'PLANNED' && <><Link className={secondaryActionClass} to={`/prints/${printJob.id}/edit`}><Pencil aria-hidden="true" className="size-4" />{t('prints.actions.edit')}</Link><button className={primaryActionClass} onClick={() => setAction('start')} type="button">{t('prints.actions.start')}</button></>}
          {printJob.status === 'PRINTING' && !printJob.capture_mode && <button className={primaryActionClass} onClick={() => setAction('finish')} type="button">{t('prints.actions.finish')}</button>}
        </div>
      </header>

      {feedback && <div className="mt-5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-ink" role="status">{feedback}</div>}

      <div className="mt-7 grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-6">
          <Overview printJob={printJob} />
          {printJob.capture_mode && <EnrichmentSection error={enrichmentMutation.isError} onRetry={() => enrichmentMutation.mutate()} printJob={printJob} retrying={enrichmentMutation.isPending} />}
          {printJob.capture_mode && <AmsSnapshotSection printJob={printJob} />}
          {!printJob.capture_mode && <SpoolsSection entries={entries} printJob={printJob} />}
          {!printJob.capture_mode && <CostsSection entries={entries} />}
          <Notes notes={printJob.notes} />
        </div>
        <Timeline printJob={printJob} />
      </div>

      {action === 'start' && <StartPrintDialog entries={entries} onCancel={() => setAction(null)} onSuccess={() => { setAction(null); setFeedback(t('prints.messages.started')) }} printJob={printJob} />}
      {action === 'finish' && <FinishPrintDialog entries={entries} onCancel={() => setAction(null)} onSuccess={() => { setAction(null); setFeedback(t('prints.messages.finished')) }} printJob={printJob} />}
    </main>
  )
}

const primaryActionClass = 'inline-flex min-h-11 items-center justify-center rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent'
const secondaryActionClass = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-line bg-surface px-4 py-2.5 text-sm font-bold text-ink hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent'

function Section({ title, icon, children, label }: { title: string; icon: React.ReactNode; children: React.ReactNode; label?: string }) {
  return <section aria-label={label ?? title} className="rounded-xl border border-line bg-surface p-5 shadow-sm sm:p-6"><div className="flex items-center gap-3"><span className="text-accent" aria-hidden="true">{icon}</span><h2 className="text-lg font-semibold text-ink">{title}</h2></div>{children}</section>
}

function Overview({ printJob }: { printJob: PrintJob }) {
  const { t } = useTranslation()
  const runningMinutes = useElapsedMinutes(printJob.status === 'PRINTING' ? printJob.started_at : null)
  const observedMinutes = printJob.actual_time_minutes ?? (printJob.duration_seconds == null ? null : Math.floor(printJob.duration_seconds / 60))
  const actualDuration = printJob.status === 'PRINTING' ? formatDuration(runningMinutes) : formatDuration(observedMinutes)
  const values = [
    [t('prints.details.status'), <PrintJobStatusBadge key="status" status={printJob.status} />],
    [t('prints.details.printer'), printJob.printer_name ?? printJob.printer_serial ?? '—'],
    [t('prints.fields.progress'), printJob.final_progress == null ? '—' : `${printJob.final_progress}%`],
    [t('prints.details.createdAt'), formatPrintDateTime(printJob.created_at)],
    [t('prints.details.startedAt'), formatPrintDateTime(printJob.started_at)],
    [t('prints.details.finishedAt'), formatPrintDateTime(printJob.finished_at)],
    [t('prints.details.estimatedTime'), formatDuration(printJob.estimated_time_minutes)],
    [t('prints.details.actualTime'), actualDuration],
    [t('prints.details.layers'), printJob.final_layer == null ? '—' : printJob.total_layers == null ? String(printJob.final_layer) : `${printJob.final_layer} / ${printJob.total_layers}`],
  ] as const
  return <Section icon={<CalendarClock className="size-5" />} title={t('prints.details.overview')}><dl className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{values.map(([label, value]) => <div key={label}><dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</dt><dd className="mt-1.5 text-sm font-semibold text-ink">{value}</dd></div>)}</dl></Section>
}

const retryableEnrichmentStates = new Set(['FILE_NOT_FOUND', 'AMBIGUOUS', 'RETRYABLE', 'FAILED'])

function EnrichmentSection({ error, onRetry, printJob, retrying }: { error: boolean; onRetry: () => void; printJob: PrintJob; retrying: boolean }) {
  const { t } = useTranslation()
  const title = printJob.name ?? printJob.gcode_file?.split('/').pop() ?? t('prints.unnamed', { id: printJob.id })
  const filaments = printJob.filaments ?? []
  const status = printJob.enrichment_status ?? 'PENDING'
  const canRetry = retryableEnrichmentStates.has(status)
  return <Section icon={<Layers3 className="size-5" />} title={t('prints.metadata.title')}>
    <div className="mt-5 grid gap-5 md:grid-cols-[14rem_minmax(0,1fr)]">
      <PrintJobThumbnail alt={title} className="aspect-square w-full" url={printJob.thumbnail_url} />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-semibold text-ink">{t(`prints.metadata.status.${status}`)}</p>
          {canRetry && <button className={secondaryActionClass} disabled={retrying} onClick={onRetry} type="button"><RefreshCw aria-hidden="true" className={`size-4 ${retrying ? 'animate-spin' : ''}`} />{retrying ? t('prints.metadata.retrying') : t('prints.metadata.retry')}</button>}
        </div>
        {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400" role="alert">{t('prints.metadata.retryError')}</p>}
        {status === 'ENRICHED' ? <>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            <SummaryValue label={t('prints.metadata.estimatedTotal')} value={printJob.estimated_filament_g == null ? '—' : formatWeight(Number(printJob.estimated_filament_g))} />
            <SummaryValue label={t('prints.metadata.estimatedLength')} value={printJob.estimated_filament_m == null ? '—' : `${Number(printJob.estimated_filament_m).toFixed(2)} m`} />
            <SummaryValue label={t('prints.metadata.slicerDuration')} value={printJob.slicer_estimated_duration_seconds == null ? '—' : formatDuration(Math.round(printJob.slicer_estimated_duration_seconds / 60))} />
            <SummaryValue label={t('prints.metadata.plate')} value={printJob.selected_plate_name ?? (printJob.selected_plate_index == null ? '—' : String(printJob.selected_plate_index))} />
          </dl>
          <div className="mt-5 space-y-3">{filaments.map((filament) => <article className="rounded-lg border border-line bg-surface-raised p-4" key={filament.id}><div className="flex items-center gap-3"><span aria-hidden="true" className="size-5 shrink-0 rounded-full border border-black/10 shadow-sm" style={{ backgroundColor: filamentColor(filament.color) ?? 'transparent' }} /><div className="min-w-0"><h3 className="font-semibold text-ink">{filament.material_type ?? t('prints.metadata.unknownMaterial')}</h3><p className="truncate font-mono text-xs text-ink-muted">{filament.color ?? t('prints.metadata.colorUnavailable')}</p></div></div><dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4"><SummaryValue label={t('prints.metadata.estimatedWeight')} value={filament.used_g == null ? '—' : `${Number(filament.used_g).toFixed(2)} g`} /><SummaryValue label={t('prints.metadata.estimatedMeters')} value={filament.used_m == null ? '—' : `${Number(filament.used_m).toFixed(2)} m`} /><SummaryValue label={t('prints.metadata.trayInfo')} value={filament.tray_info_idx ?? '—'} /><SummaryValue label={t('prints.metadata.nozzle')} value={filament.nozzle_diameter == null ? '—' : `${Number(filament.nozzle_diameter).toFixed(2)} mm`} /></dl>{filament.reconciliation_event_type && <div className="mt-4 border-t border-line pt-3 text-sm font-semibold text-ink">{filament.reconciliation_event_type === 'SKIP' ? t('prints.details.reconciliationSkipped') : <>{t('prints.details.reconciledSpool')}: <Link className="font-mono text-accent hover:underline" to={`/spools/${encodeURIComponent(filament.confirmed_spool_code ?? String(filament.confirmed_spool_id))}`}>{filament.confirmed_spool_code ?? t('prints.spoolFallback', { id: filament.confirmed_spool_id })}</Link>{filament.reconciled_consumption_g != null && <> · {formatWeight(Number(filament.reconciled_consumption_g))}</>}</>}</div>}</article>)}</div>
        </> : <p className="mt-4 text-sm leading-6 text-ink-muted">{t('prints.metadata.unavailableDescription')}</p>}
        <p className="mt-4 text-xs text-ink-muted">{t('prints.metadata.estimateDisclaimer')}</p>
      </div>
    </div>
  </Section>
}

function AmsSnapshotSection({ printJob }: { printJob: PrintJob }) {
  const { t } = useTranslation()
  const units = printJob.ams_snapshot?.ams_units ?? []
  const trays = units.flatMap((unit) => (unit.trays ?? []).map((tray) => ({ ...tray, unitId: unit.unit_id })))
  if (printJob.ams_snapshot?.external_tray) trays.push({ ...printJob.ams_snapshot.external_tray, unitId: t('prints.metadata.external') })
  return <Section icon={<Boxes className="size-5" />} title={t('prints.metadata.amsSnapshot')}>
    {trays.length ? <div className="mt-5 grid gap-3 sm:grid-cols-2">{trays.map((tray, index) => <article className="rounded-lg border border-line bg-surface-raised p-4" key={`${tray.unitId}-${tray.tray_id}-${index}`}><div className="flex items-center gap-3"><span aria-hidden="true" className="size-4 shrink-0 rounded-full border border-black/10" style={{ backgroundColor: filamentColor(tray.color ?? null) ?? 'transparent' }} /><strong className="text-sm text-ink">{tray.unitId} · {t('printerStatus.tray', { id: tray.tray_id })}</strong></div><p className="mt-2 text-sm text-ink-muted">{[tray.brand, tray.material_type].filter(Boolean).join(' · ') || t('printerStatus.emptyTray')}</p>{tray.remaining_percent != null && <p className="mt-1 text-xs text-ink-muted">{t('prints.metadata.snapshotRemaining', { value: tray.remaining_percent })}</p>}</article>)}</div> : <p className="mt-4 text-sm text-ink-muted">{t('prints.amsUnavailable')}</p>}
    <p className="mt-4 text-xs text-ink-muted">{t('prints.metadata.snapshotDisclaimer')}</p>
  </Section>
}

function SpoolsSection({ entries, printJob }: { entries: ResolvedPrintJobSpool[]; printJob: PrintJob }) {
  const { t } = useTranslation()
  const estimatedComplete = printJob.spools.every((link) => link.estimated_weight_g != null)
  const actualComplete = printJob.spools.every((link) => link.actual_weight_g != null)
  const estimatedTotal = estimatedComplete ? numericTotal(printJob.total_estimated_weight_g, printJob.spools, 'estimated_weight_g') : null
  const actualTotal = actualComplete ? numericTotal(printJob.total_actual_weight_g, printJob.spools, 'actual_weight_g') : null
  return <Section icon={<Boxes className="size-5" />} label={t('prints.details.spools')} title={t('prints.details.spools')}>
    <dl className="mt-5 grid gap-4 rounded-lg bg-surface-raised p-4 sm:grid-cols-2">
      <SummaryValue label={t('prints.details.totalEstimatedWeight')} value={estimatedComplete && estimatedTotal != null ? formatWeight(estimatedTotal) : t('prints.details.incompleteEstimate')} />
      <SummaryValue label={t('prints.details.totalConsumedWeight')} value={actualComplete && actualTotal != null ? formatWeight(actualTotal) : t('prints.details.partialConsumption')} />
    </dl>
    <div className="mt-5 grid gap-4 lg:grid-cols-2">{entries.map((entry) => <SpoolBreakdown key={entry.link.id} entry={entry} />)}</div>
  </Section>
}

function numericTotal(value: PrintJob['total_actual_weight_g'], links: PrintJobSpool[], field: 'estimated_weight_g' | 'actual_weight_g'): number | null {
  if (value != null && Number.isFinite(Number(value))) return Number(value)
  let total = 0
  for (const link of links) {
    const item = link[field]
    if (item == null || !Number.isFinite(Number(item))) return null
    total += Number(item)
  }
  return total
}

function SummaryValue({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</dt><dd className="mt-1 text-base font-semibold text-ink">{value}</dd></div>
}

function SpoolBreakdown({ entry }: { entry: ResolvedPrintJobSpool }) {
  const { t } = useTranslation()
  const { link, spool } = entry
  const currency = link.material_cost_currency
  return <article className="min-w-0 rounded-lg border border-line bg-surface-raised p-4" aria-label={spool?.display_name ?? spool?.code ?? t('prints.spoolFallback', { id: link.spool_id })}>
    <div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="break-words text-base font-semibold text-ink">{spool?.display_name ?? spool?.code ?? t('prints.spoolFallback', { id: link.spool_id })}</h3><p className="mt-1 font-mono text-xs text-ink-muted">{spool?.code ?? t('prints.spoolFallback', { id: link.spool_id })}</p></div>{spool?.status === 'ARCHIVED' && <SpoolStatusBadge status="ARCHIVED" />}</div>
    {spool && <p className="mt-3 text-sm text-ink-muted">{spool.manufacturer.name} · {spool.material.name} · {spool.color_name}</p>}
    <dl className="mt-4 grid grid-cols-2 gap-4">
      <SummaryValue label={t('prints.details.estimatedWeight')} value={link.estimated_weight_g == null ? '—' : formatWeight(Number(link.estimated_weight_g))} />
      <SummaryValue label={t('prints.details.consumedWeight')} value={link.actual_weight_g == null ? t('prints.details.consumptionNotProvided') : formatWeight(Number(link.actual_weight_g))} />
      <SummaryValue label={t('prints.details.unitCost')} value={link.filament_cost_per_g == null || !currency ? '—' : `${formatCurrency(link.filament_cost_per_g, currency)}/g`} />
      <SummaryValue label={t('prints.details.materialCost')} value={link.material_cost == null || !currency ? '—' : formatCurrency(link.material_cost, currency)} />
    </dl>
    {spool && <Link className="mt-5 inline-flex rounded-md border border-line bg-surface px-3 py-2 text-sm font-bold text-ink hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" to={`/spools/${encodeURIComponent(spool.code)}`}>{t('prints.details.viewSpool')}</Link>}
  </article>
}

function CostsSection({ entries }: { entries: ResolvedPrintJobSpool[] }) {
  const { t } = useTranslation()
  const groups = new Map<string, number>()
  let unavailable = 0
  for (const { link } of entries) {
    if (link.material_cost == null || !link.material_cost_currency) unavailable += 1
    else groups.set(link.material_cost_currency, (groups.get(link.material_cost_currency) ?? 0) + Number(link.material_cost))
  }
  const totals = [...groups.entries()]
  const complete = unavailable === 0
  const title = complete && totals.length === 1 ? t('prints.details.totalMaterialCost') : complete ? t('prints.details.materialCosts') : t('prints.details.knownCost')
  return <Section icon={<CircleDollarSign className="size-5" />} title={t('prints.details.costs')}>
    <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
    {totals.length ? <ul className="mt-2 flex flex-wrap gap-x-6 gap-y-2">{totals.map(([currency, amount]) => <li className="text-lg font-semibold text-ink" key={currency}>{formatCurrency(amount, currency)}</li>)}</ul> : <p className="mt-2 text-sm font-semibold text-ink">—</p>}
    {unavailable > 0 && <p className="mt-3 text-sm text-ink-muted">{t('prints.details.costUnavailable')}</p>}
  </Section>
}

function Timeline({ printJob }: { printJob: PrintJob }) {
  const { t } = useTranslation()
  const events: { label: string; date: string | null; current?: boolean }[] = [{ label: t('prints.timeline.created'), date: printJob.created_at }]
  if (printJob.started_at) events.push({ label: t('prints.timeline.started'), date: printJob.started_at })
  if ((printJob.status === 'SUCCESS' || printJob.status === 'COMPLETED') && printJob.finished_at) events.push({ label: t('prints.timeline.finished'), date: printJob.finished_at })
  if (printJob.status === 'PRINTING') events.push({ label: t('prints.timeline.running'), date: null, current: true })
  return <Section icon={<CalendarClock className="size-5" />} title={t('prints.details.timeline')}>
    <ol className="mt-6 space-y-0">{events.map((event, index) => <li className="relative grid grid-cols-[1.25rem_1fr] gap-3 pb-7 last:pb-0" key={`${event.label}-${index}`}><span className={`relative z-10 mt-1 size-3 rounded-full ring-4 ring-surface ${event.current ? 'bg-accent' : 'bg-ink-muted'}`} aria-hidden="true" />{index < events.length - 1 && <span className="absolute left-[0.34rem] top-4 h-full w-px bg-line" aria-hidden="true" />}<div><h3 className="text-sm font-semibold text-ink">{event.label}</h3>{event.date && <time className="mt-1 block text-sm text-ink-muted" dateTime={event.date}>{formatPrintDateTime(event.date)}</time>}</div></li>)}</ol>
    {(printJob.status === 'FAILED' || printJob.status === 'CANCELLED' || printJob.status === 'UNKNOWN_TERMINAL') && <p className="mt-6 border-t border-line pt-4 text-sm text-ink-muted">{t('prints.details.currentStatus')}: <strong className="text-ink">{t(`prints.status.${printJob.status}`)}</strong></p>}
  </Section>
}

function Notes({ notes }: { notes: string | null }) {
  const { t } = useTranslation()
  return <Section icon={<StickyNote className="size-5" />} title={t('prints.details.notes')}><p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-ink-muted">{notes?.trim() || t('prints.details.noNotes')}</p></Section>
}

function PrintDetailsSkeleton() {
  const { t } = useTranslation()
  return <main aria-busy="true" aria-label={t('prints.details.loading')} role="status"><div className="h-5 w-40 animate-pulse rounded bg-line" /><div className="mt-6 h-20 animate-pulse rounded-lg bg-line" /><div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">{Array.from({ length: 4 }, (_, index) => <div className="h-56 animate-pulse rounded-xl border border-line bg-surface" key={index} />)}</div></main>
}

function PrintNotFound() {
  const { t } = useTranslation()
  return <main aria-labelledby="print-not-found-title" className="rounded-lg border border-line bg-surface px-5 py-12 text-center shadow-sm"><h1 className="text-xl font-semibold text-ink" id="print-not-found-title">{t('prints.details.notFound')}</h1><Link className={`${primaryActionClass} mt-6`} to="/prints">{t('prints.details.back')}</Link></main>
}

function PrintLoadError({ isFetching, onRetry }: { isFetching: boolean; onRetry: () => void }) {
  const { t } = useTranslation()
  return <main className="rounded-lg border border-red-500/30 bg-surface px-5 py-12 text-center shadow-sm" role="alert"><AlertCircle aria-hidden="true" className="mx-auto size-6 text-red-600 dark:text-red-400" /><h1 className="mt-4 text-xl font-semibold text-ink">{t('prints.details.loadError')}</h1><button className={`${primaryActionClass} mt-6 disabled:opacity-60`} disabled={isFetching} onClick={onRetry} type="button">{isFetching ? t('prints.retrying') : t('common.retry')}</button></main>
}
