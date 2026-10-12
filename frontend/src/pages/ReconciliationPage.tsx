import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  RotateCcw,
  Scale,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { isApiError } from '../api/client'
import { filamentColor, PrintJobThumbnail } from '../components/prints/PrintJobThumbnail'
import { PrintJobStatusBadge } from '../components/prints/PrintJobStatusBadge'
import { SpoolSearchCombobox } from '../components/reconciliation/SpoolSearchCombobox'
import {
  useConfirmReconciliation,
  useReconciliationQueue,
  useUndoReconciliation,
} from '../hooks/useReconciliation'
import type {
  ReconciliationConfirmItem,
  ReconciliationJob,
  ReconciliationSpoolOption,
  ReconciliationUsage,
} from '../types/reconciliation'

type Draft = {
  selected: boolean
  action: 'DEDUCT' | 'SKIP' | null
  spoolId: number | null
  consumption: string
  reason: string
  checkpointAcknowledged: boolean
}

export function ReconciliationPage() {
  const { i18n, t } = useTranslation()
  const queue = useReconciliationQueue()
  const confirm = useConfirmReconciliation()
  const undo = useUndoReconciliation()
  const [drafts, setDrafts] = useState<Record<number, Draft>>({})
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    if (!queue.data) return
    setDrafts((previous) => {
      const next: Record<number, Draft> = {}
      for (const job of queue.data.jobs) {
        for (const usage of job.filaments) {
          if (usage.resolution) continue
          next[usage.id] = previous[usage.id] ?? {
            selected: false,
            action: usage.recommended_spool_id ? 'DEDUCT' : null,
            spoolId: usage.recommended_spool_id,
            consumption: decimalText(
              usage.progress_estimated_g
              ?? (usage.requires_manual_consumption ? null : usage.used_g),
            ),
            reason: '',
            checkpointAcknowledged: false,
          }
        }
      }
      return next
    })
  }, [queue.data])

  const usageById = useMemo(() => {
    const entries = queue.data?.jobs.flatMap((job) =>
      job.filaments.map((usage) => [usage.id, usage] as const),
    ) ?? []
    return new Map(entries)
  }, [queue.data])
  const spoolById = useMemo(
    () => new Map((queue.data?.available_spools ?? []).map((spool) => [spool.id, spool])),
    [queue.data?.available_spools],
  )
  const printedAtByUsage = useMemo(() => new Map(
    (queue.data?.jobs ?? []).flatMap((job) => job.filaments.map((usage) => [usage.id, job.finished_at ?? job.started_at] as const)),
  ), [queue.data?.jobs])

  const selectedDrafts = Object.entries(drafts).filter(([, draft]) => draft.selected)
  const invalidSelected = selectedDrafts.some(([id, draft]) =>
    !draftToItem(Number(id), draft, usageById.get(Number(id)), spoolById, printedAtByUsage.get(Number(id))),
  )
  const items = selectedDrafts
    .map(([id, draft]) => draftToItem(Number(id), draft, usageById.get(Number(id)), spoolById, printedAtByUsage.get(Number(id))))
    .filter((item): item is ReconciliationConfirmItem => item !== null)

  const groups = useMemo(
    () => groupJobsByDay(queue.data?.jobs ?? [], i18n.resolvedLanguage),
    [i18n.resolvedLanguage, queue.data?.jobs],
  )

  function updateDraft(id: number, changes: Partial<Draft>) {
    setNotice(null)
    setDrafts((current) => ({
      ...current,
      [id]: { ...current[id], ...changes },
    }))
  }

  function selectReady() {
    setNotice(null)
    setDrafts((current) => {
      const next = { ...current }
      for (const job of queue.data?.jobs ?? []) {
        for (const usage of job.filaments) {
          if (usage.resolution || !usage.unambiguous || usage.requires_manual_consumption) continue
          next[usage.id] = {
            ...(next[usage.id] ?? {
              action: 'DEDUCT',
              spoolId: usage.recommended_spool_id,
              consumption: decimalText(usage.used_g),
              reason: '',
              checkpointAcknowledged: false,
            }),
            selected: true,
            action: 'DEDUCT',
            spoolId: usage.recommended_spool_id,
          }
        }
      }
      return next
    })
  }

  async function submit() {
    if (!items.length || invalidSelected) return
    setNotice(null)
    try {
      await confirm.mutateAsync(items)
      setNotice(t('reconciliation.confirmed', { count: items.length }))
    } catch (error) {
      setNotice(reconciliationError(error, t))
    }
  }

  async function reverse(usageId: number) {
    const reason = window.prompt(t('reconciliation.undoPrompt'))?.trim()
    if (!reason) return
    setNotice(null)
    try {
      await undo.mutateAsync({ usageId, reason })
      setNotice(t('reconciliation.undone'))
    } catch (error) {
      setNotice(reconciliationError(error, t))
    }
  }

  if (queue.isPending) return <ReconciliationLoading />

  if (queue.error || !queue.data) {
    return (
      <section aria-labelledby="reconciliation-title">
        <PageHeading />
        <div className="rounded-lg border border-red-500/30 bg-surface p-8 text-center" role="alert">
          <AlertTriangle aria-hidden="true" className="mx-auto size-7 text-red-500" />
          <p className="mt-3 font-semibold text-ink">{t('reconciliation.loadError')}</p>
          <button className="mt-4 rounded-md bg-accent px-4 py-2 text-sm font-bold text-sidebar" onClick={() => void queue.refetch()} type="button">
            {t('common.retry')}
          </button>
        </div>
      </section>
    )
  }

  return (
    <section aria-labelledby="reconciliation-title">
      <PageHeading />

      <div className="grid gap-3 sm:grid-cols-3">
        <SummaryCard label={t('reconciliation.pending')} value={String(queue.data.pending_job_count)} />
        <SummaryCard label={t('reconciliation.ready')} tone="good" value={String(queue.data.ready_job_count)} />
        <SummaryCard label={t('reconciliation.estimatedPending')} value={`${formatWeight(queue.data.estimated_pending_g)} g`} />
      </div>

      {queue.data.jobs.length === 0 ? (
        <div className="mt-6 rounded-lg border border-line bg-surface px-5 py-14 text-center shadow-sm">
          <CheckCircle2 aria-hidden="true" className="mx-auto size-9 text-emerald-500" />
          <h3 className="mt-4 text-lg font-semibold text-ink">{t('reconciliation.empty')}</h3>
          <p className="mt-2 text-sm text-ink-muted">{t('reconciliation.emptyDescription')}</p>
        </div>
      ) : (
        <>
          <div className="sticky top-16 z-20 mt-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface/95 p-3 shadow-sm backdrop-blur lg:top-[4.5rem]">
            <div>
              <p className="text-sm font-semibold text-ink">{t('reconciliation.batchTitle')}</p>
              <p className="text-xs text-ink-muted">{t('reconciliation.selectedLines', { count: selectedDrafts.length })}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink hover:border-accent/50" onClick={selectReady} type="button">
                {t('reconciliation.selectReady')}
              </button>
              <button
                className="rounded-md bg-accent px-4 py-2 text-sm font-bold text-sidebar disabled:cursor-not-allowed disabled:opacity-50"
                disabled={!items.length || invalidSelected || confirm.isPending}
                onClick={() => void submit()}
                type="button"
              >
                {confirm.isPending ? t('reconciliation.confirming') : t('reconciliation.confirmSelected', { count: selectedDrafts.length })}
              </button>
            </div>
          </div>
          {invalidSelected && <p className="mt-2 text-sm text-red-600" role="alert">{t('reconciliation.fixSelected')}</p>}
          {notice && <p className="mt-3 rounded-md border border-line bg-surface px-4 py-3 text-sm text-ink" role="status">{notice}</p>}

          <div className="mt-6 space-y-8">
            {groups.map(([label, jobs]) => (
              <section aria-labelledby={`day-${jobs[0].id}`} key={label}>
                <div className="mb-3 flex items-end justify-between gap-3 border-b border-line pb-2">
                  <h3 className="text-lg font-semibold text-ink" id={`day-${jobs[0].id}`}>{label}</h3>
                  <span className="text-sm text-ink-muted">{t('reconciliation.printCount', { count: jobs.length })}</span>
                </div>
                <div className="space-y-4">
                  {jobs.map((job) => (
                    <PrintReconciliationCard
                      availableSpools={queue.data.available_spools}
                      drafts={drafts}
                      job={job}
                      key={job.id}
                      onChange={updateDraft}
                      onUndo={reverse}
                      undoing={undo.isPending}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </>
      )}
      {queue.data.recently_reconciled_jobs.length > 0 && (
        <section aria-labelledby="recently-reconciled-title" className="mt-10">
          <div className="mb-3 border-b border-line pb-2">
            <h3 className="text-lg font-semibold text-ink" id="recently-reconciled-title">{t('reconciliation.recentTitle')}</h3>
            <p className="mt-1 text-sm text-ink-muted">{t('reconciliation.recentDescription')}</p>
          </div>
          <div className="space-y-4">
            {queue.data.recently_reconciled_jobs.map((job) => (
              <PrintReconciliationCard
                availableSpools={queue.data.available_spools}
                drafts={{}}
                job={job}
                key={job.id}
                onChange={() => undefined}
                onUndo={reverse}
                undoing={undo.isPending}
              />
            ))}
          </div>
        </section>
      )}
    </section>
  )
}

function PageHeading() {
  const { t } = useTranslation()
  return (
    <div className="mb-6">
      <div className="mb-3 flex items-center gap-3">
        <span aria-hidden="true" className="h-px w-8 bg-accent" />
        <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">{t('reconciliation.eyebrow')}</p>
      </div>
      <h2 className="text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl" id="reconciliation-title">{t('reconciliation.title')}</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-ink-muted sm:text-base">{t('reconciliation.description')}</p>
    </div>
  )
}

function ReconciliationLoading() {
  const { t } = useTranslation()
  return (
    <section aria-busy="true" aria-label={t('reconciliation.loading')}>
      <PageHeading />
      <div className="grid animate-pulse gap-4">
        <div className="h-24 rounded-lg bg-surface" />
        <div className="h-72 rounded-lg bg-surface" />
      </div>
    </section>
  )
}

function SummaryCard({ label, tone, value }: { label: string; tone?: 'good'; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</p>
      <p className={`mt-2 font-mono text-2xl font-bold ${tone === 'good' ? 'text-emerald-600 dark:text-emerald-400' : 'text-ink'}`}>{value}</p>
    </div>
  )
}

function PrintReconciliationCard({
  availableSpools,
  drafts,
  job,
  onChange,
  onUndo,
  undoing,
}: {
  availableSpools: ReconciliationSpoolOption[]
  drafts: Record<number, Draft>
  job: ReconciliationJob
  onChange: (id: number, changes: Partial<Draft>) => void
  onUndo: (id: number) => Promise<void>
  undoing: boolean
}) {
  const { i18n, t } = useTranslation()
  const time = job.finished_at ?? job.started_at
  const resolved = job.filaments.filter((usage) => usage.resolution).length
  return (
    <details className="group rounded-lg border border-line bg-surface shadow-sm" open>
      <summary className="flex cursor-pointer list-none items-start gap-4 p-4 sm:p-5">
        <PrintJobThumbnail alt={job.name ?? t('reconciliation.unnamedPrint')} className="size-24 sm:size-28" url={job.thumbnail_url} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <h4 className="truncate text-lg font-semibold text-ink">{job.name ?? job.gcode_file ?? t('reconciliation.unnamedPrint')}</h4>
              <p className="mt-1 text-sm text-ink-muted">{time ? formatDateTime(time, i18n.resolvedLanguage) : t('reconciliation.dateUnavailable')}</p>
            </div>
            <PrintJobStatusBadge status={job.status} />
          </div>
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm text-ink-muted">
            <span>{formatDuration(job.duration_seconds, job.actual_time_minutes)}</span>
            <span>{job.selected_plate_index === null ? t('reconciliation.plateUnavailable') : t('reconciliation.plate', { plate: job.selected_plate_index })}</span>
            <span>{t('reconciliation.filamentCount', { count: job.filament_count })}</span>
            <span>{formatWeight(job.estimated_filament_g)} g {t('reconciliation.slicedEstimateShort')}</span>
          </div>
          <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">{resolved}/{job.filament_count} {t('reconciliation.resolved')}</p>
        </div>
        <ChevronDown aria-hidden="true" className="mt-1 size-5 shrink-0 text-ink-muted transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-line p-4 sm:p-5">
        {job.status !== 'COMPLETED' && job.status !== 'SUCCESS' && (
          <div className="mb-4 flex gap-3 rounded-md border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-ink">
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-amber-600" />
            <p><strong>{t('reconciliation.incompleteTitle')}</strong> {t('reconciliation.incompleteDescription', { progress: job.final_progress ?? '—' })}</p>
          </div>
        )}
        <div className="space-y-4">
          {job.filaments.map((usage) => usage.resolution ? (
            <ResolvedUsage key={usage.id} onUndo={onUndo} undoing={undoing} usage={usage} />
          ) : (
            <PendingUsage availableSpools={availableSpools} draft={drafts[usage.id]} finalProgress={job.final_progress} key={usage.id} onChange={onChange} printedAt={job.finished_at ?? job.started_at} usage={usage} />
          ))}
        </div>
      </div>
    </details>
  )
}

function PendingUsage({ availableSpools, draft, finalProgress, onChange, printedAt, usage }: { availableSpools: ReconciliationSpoolOption[]; draft?: Draft; finalProgress: number | null; onChange: (id: number, changes: Partial<Draft>) => void; printedAt: string | null; usage: ReconciliationUsage }) {
  const { t } = useTranslation()
  if (!draft) return null
  const selectedCandidate = usage.candidates.find((candidate) => candidate.id === draft.spoolId)
  const selectedSpool = availableSpools.find((spool) => spool.id === draft.spoolId)
  const enteredAmount = Number(draft.consumption)
  const hasEnough = selectedSpool
    ? Number(selectedSpool.current_filament_weight_g) >= enteredAmount
    : false
  const manual = usage.requires_manual_consumption || (
    draft.consumption !== '' && Number(draft.consumption) !== Number(usage.used_g)
  )
  const checkpointWarning = hasCheckpointConflict(printedAt, selectedSpool?.latest_physical_calibration_at)
  return (
    <article className={`rounded-md border p-4 ${draft.selected ? 'border-accent bg-accent-soft/30' : 'border-line bg-canvas/30'}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <input
            aria-label={t('reconciliation.includeUsage', { material: usage.material_type ?? '' })}
            checked={draft.selected}
            className="mt-1 size-4 accent-[var(--accent)]"
            onChange={(event) => onChange(usage.id, { selected: event.target.checked })}
            type="checkbox"
          />
          <span aria-hidden="true" className="mt-0.5 size-5 shrink-0 rounded-full border border-black/10" style={{ backgroundColor: filamentColor(usage.color) ?? 'transparent' }} />
          <div>
            <h5 className="font-semibold text-ink">{usage.material_type ?? t('reconciliation.unknownMaterial')}</h5>
            <p className="mt-1 text-sm text-ink-muted">{formatWeight(usage.used_g)} g · {usage.ams_tray ?? t('reconciliation.trayUnavailable')}{usage.ams_brand ? ` · ${usage.ams_brand}` : ''}</p>
          </div>
        </div>
        {usage.unambiguous ? <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300">{t('reconciliation.ready')}</span> : <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:text-amber-300">{t('reconciliation.needsSelection')}</span>}
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_9rem]">
        <SpoolSearchCombobox
          label={t('reconciliation.physicalSpool')}
          onSelect={(spoolId) => onChange(usage.id, { action: 'DEDUCT', spoolId, checkpointAcknowledged: false })}
          onSkip={() => onChange(usage.id, { action: 'SKIP', spoolId: null })}
          selectedSpoolId={draft.spoolId}
          skipped={draft.action === 'SKIP'}
          spools={availableSpools}
          suggestedSpoolIds={usage.candidates.map((candidate) => candidate.id)}
        />
        {draft.action === 'DEDUCT' && (
          <label className="text-sm font-medium text-ink">
            {t('reconciliation.consumption')}
            <div className="relative mt-1.5">
              <input className="w-full rounded-md border border-line bg-surface px-3 py-2.5 pr-8 text-sm text-ink" min="0.001" onChange={(event) => onChange(usage.id, { consumption: event.target.value })} step="0.001" type="number" value={draft.consumption} />
              <span className="absolute right-3 top-2.5 text-sm text-ink-muted">g</span>
            </div>
            {usage.requires_manual_consumption && usage.progress_estimated_g != null && (
              <span className="mt-1.5 block text-xs font-normal text-ink-muted">
                {t('reconciliation.progressEstimate', {
                  estimate: formatWeight(usage.progress_estimated_g),
                  progress: finalProgress ?? '—',
                  total: formatWeight(usage.used_g),
                })}
              </span>
            )}
          </label>
        )}
      </div>

      {selectedCandidate && (
        <div className={`mt-3 rounded-md border px-3 py-2.5 text-xs ${hasEnough || !Number.isFinite(enteredAmount) ? 'border-line text-ink-muted' : 'border-red-500/30 bg-red-500/5 text-red-700 dark:text-red-300'}`}>
          <p className="font-semibold text-ink">{t(`reconciliation.confidence.${selectedCandidate.confidence}`)}</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {selectedCandidate.reasons.map((reason) => <li key={reason.code}>{reason.detail}</li>)}
          </ul>
          {!hasEnough && Number.isFinite(enteredAmount) && enteredAmount > 0 && <p className="mt-2 font-semibold">{t('reconciliation.insufficient')}</p>}
        </div>
      )}
      {!selectedCandidate && selectedSpool && draft.action === 'DEDUCT' && (
        <div className={`mt-3 rounded-md border px-3 py-2.5 text-xs ${hasEnough || !Number.isFinite(enteredAmount) ? 'border-amber-500/30 bg-amber-500/5 text-ink' : 'border-red-500/30 bg-red-500/5 text-red-700 dark:text-red-300'}`}>
          <p className="font-semibold">{t('reconciliation.manualSpoolSelection')}</p>
          {!hasEnough && Number.isFinite(enteredAmount) && enteredAmount > 0 && <p className="mt-2 font-semibold">{t('reconciliation.insufficient')}</p>}
        </div>
      )}

      {checkpointWarning && draft.action === 'DEDUCT' && (
        <div className="mt-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-ink">
          <p className="font-semibold">{t('reconciliation.checkpointWarning')}</p>
          <p className="mt-1 text-ink-muted">{t('reconciliation.checkpointWarningHelp')}</p>
          <label className="mt-3 flex items-start gap-2 font-medium"><input checked={draft.checkpointAcknowledged} className="mt-0.5 accent-[var(--accent)]" onChange={(event) => onChange(usage.id, { checkpointAcknowledged: event.target.checked })} type="checkbox" />{t('reconciliation.checkpointAcknowledge')}</label>
        </div>
      )}

      {(draft.action === 'SKIP' || manual) && (
        <label className="mt-3 block text-sm font-medium text-ink">
          {manual ? t('reconciliation.reasonRequired') : t('reconciliation.reasonOptional')}
          <input className="mt-1.5 w-full rounded-md border border-line bg-surface px-3 py-2.5 text-sm text-ink" maxLength={500} onChange={(event) => onChange(usage.id, { reason: event.target.value })} placeholder={t('reconciliation.reasonPlaceholder')} value={draft.reason} />
        </label>
      )}
      <p className="mt-3 flex items-center gap-1.5 text-xs text-ink-muted"><Scale aria-hidden="true" className="size-3.5" />{t('reconciliation.estimateNotice')}</p>
    </article>
  )
}

function ResolvedUsage({ onUndo, undoing, usage }: { onUndo: (id: number) => Promise<void>; undoing: boolean; usage: ReconciliationUsage }) {
  const { t } = useTranslation()
  const resolution = usage.resolution!
  return (
    <article className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-emerald-500/30 bg-emerald-500/5 p-4">
      <div>
        <p className="font-semibold text-ink">{usage.material_type ?? t('reconciliation.unknownMaterial')} · {formatWeight(usage.used_g)} g {t('reconciliation.slicedEstimateShort')}</p>
        <p className="mt-1 text-sm text-ink-muted">
          {resolution.event_type === 'SKIP'
            ? t('reconciliation.skipped')
            : t('reconciliation.deducted', { amount: formatWeight(resolution.amount_g), spool: resolution.spool_code })}
          {resolution.manual_override ? ` · ${t('reconciliation.manualAmount')}` : ''}
        </p>
      </div>
      <button className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink hover:border-accent/50 disabled:opacity-50" disabled={undoing} onClick={() => void onUndo(usage.id)} type="button">
        <RotateCcw aria-hidden="true" className="size-4" />{t('reconciliation.undo')}
      </button>
    </article>
  )
}

function draftToItem(id: number, draft: Draft, usage: ReconciliationUsage | undefined, spools: Map<number, ReconciliationSpoolOption>, printedAt?: string | null): ReconciliationConfirmItem | null {
  if (!usage || !draft.action) return null
  if (draft.action === 'SKIP') {
    return { filament_usage_id: id, action: 'SKIP', ...(draft.reason.trim() ? { reason: draft.reason.trim() } : {}) }
  }
  const amount = Number(draft.consumption)
  const spool = draft.spoolId ? spools.get(draft.spoolId) : undefined
  const manual = usage.requires_manual_consumption || amount !== Number(usage.used_g)
  const checkpointWarning = hasCheckpointConflict(printedAt, spool?.latest_physical_calibration_at)
  if (!draft.spoolId || !spool || !Number.isFinite(amount) || amount <= 0 || amount > Number(spool.current_filament_weight_g) || (manual && !draft.reason.trim()) || (checkpointWarning && !draft.checkpointAcknowledged)) return null
  return {
    filament_usage_id: id,
    action: 'DEDUCT',
    spool_id: draft.spoolId,
    consumption_g: amount,
    ...(checkpointWarning ? { checkpoint_acknowledged: true } : {}),
    ...(draft.reason.trim() ? { reason: draft.reason.trim() } : {}),
  }
}

function hasCheckpointConflict(printedAt?: string | null, calibratedAt?: string | null): boolean {
  if (!printedAt || !calibratedAt) return false
  const printed = new Date(printedAt).getTime()
  const calibrated = new Date(calibratedAt).getTime()
  return Number.isFinite(printed) && Number.isFinite(calibrated) && printed <= calibrated
}

function groupJobsByDay(jobs: ReconciliationJob[], language?: string): [string, ReconciliationJob[]][] {
  const groups = new Map<string, { label: string; jobs: ReconciliationJob[] }>()
  for (const job of jobs) {
    const raw = job.finished_at ?? job.started_at
    const date = raw ? new Date(raw) : null
    const key = date && !Number.isNaN(date.getTime()) ? date.toISOString().slice(0, 10) : 'unknown'
    const label = date && !Number.isNaN(date.getTime())
      ? new Intl.DateTimeFormat(language === 'en' ? 'en' : 'pt-BR', { dateStyle: 'full' }).format(date)
      : '—'
    const group = groups.get(key) ?? { label, jobs: [] }
    group.jobs.push(job)
    groups.set(key, group)
  }
  return [...groups.values()].map((group) => [group.label, group.jobs])
}

function decimalText(value: string | number | null): string {
  return value === null ? '' : String(value)
}

function formatWeight(value: string | number | null): string {
  if (value === null) return '—'
  const number = Number(value)
  return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 3 }) : String(value)
}

function formatDateTime(value: string, language?: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(language === 'en' ? 'en' : 'pt-BR', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function formatDuration(seconds: number | null, minutes: number | null): string {
  const totalMinutes = seconds === null ? minutes : Math.round(seconds / 60)
  if (totalMinutes === null) return '—'
  const hours = Math.floor(totalMinutes / 60)
  const rest = totalMinutes % 60
  return hours ? `${hours}h ${rest}m` : `${rest}m`
}

function reconciliationError(error: unknown, t: (key: string, options?: Record<string, unknown>) => string): string {
  if (isApiError(error) && typeof error.detail === 'object' && error.detail && 'detail' in error.detail) {
    const detail = (error.detail as { detail?: { code?: string } }).detail
    if (detail?.code === 'insufficient_weight') return t('reconciliation.errors.insufficient')
    if (detail?.code === 'manual_reason_required') return t('reconciliation.errors.reason')
    if (detail?.code === 'spool_unavailable') return t('reconciliation.errors.spool')
    if (detail?.code === 'reconciliation_conflict' || detail?.code === 'reversal_conflict') return t('reconciliation.errors.conflict')
  }
  return t('reconciliation.errors.generic')
}
