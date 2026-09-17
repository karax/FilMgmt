import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { isApiError } from '../../api/client'
import { useFinishPrintJob, useStartPrintJob } from '../../hooks/usePrintJobMutations'
import { formatPercent, formatWeight } from '../../lib/inventory'
import { apiDetailMessage, mapFinishValidationErrors } from '../../lib/printLifecycleValidation'
import type { PrintJob, PrintJobFinishPayload, PrintJobSpool } from '../../types/printJob'
import type { Spool } from '../../types/spool'

export type ResolvedPrintJobSpool = { link: PrintJobSpool; spool: Spool | undefined }

type DialogBaseProps = {
  printJob: PrintJob
  entries: ResolvedPrintJobSpool[]
  onCancel: () => void
  onSuccess: () => void
}

function spoolTitle(entry: ResolvedPrintJobSpool, fallback: string): string {
  return entry.spool?.display_name ?? entry.spool?.code ?? fallback
}

function lifecycleError(error: unknown, phase: 'start' | 'finish', t: (key: string) => string): string {
  if (!isApiError(error)) return phase === 'finish' ? t('prints.finish.networkError') : t('prints.start.networkError')
  const detail = apiDetailMessage(error)?.toLowerCase() ?? ''
  if (detail.includes('already in use') || detail.includes('already using')) return t('prints.errors.alreadyInUse')
  if (detail.includes('empty spool')) return t('prints.errors.emptySpool')
  if (detail.includes('archived spool')) return t('prints.errors.archivedSpool')
  if (detail.includes('planned print')) return t('prints.errors.notPlanned')
  if (detail.includes('printing job')) return t('prints.errors.notPrinting')
  if (detail.includes('exceeds available')) return t('prints.errors.insufficientFilament')
  return phase === 'finish' ? t('prints.finish.error') : t('prints.start.error')
}

function DialogFrame({ title, description, cancelLabel, pending, onCancel, children, actions }: {
  title: string
  description: string
  cancelLabel: string
  pending: boolean
  onCancel: () => void
  children: React.ReactNode
  actions: React.ReactNode
}) {
  const cancelRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    cancelRef.current?.focus()
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !pending) onCancel()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onCancel, pending])

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-3 sm:p-5" role="presentation">
      <div aria-describedby="print-action-description" aria-labelledby="print-action-title" aria-modal="true" className="flex max-h-[calc(100dvh-1.5rem)] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-2xl sm:max-h-[calc(100dvh-2.5rem)]" role="dialog">
        <header className="border-b border-line px-5 py-4 sm:px-6">
          <h2 className="text-lg font-semibold text-ink" id="print-action-title">{title}</h2>
          <p className="mt-1.5 text-sm leading-6 text-ink-muted" id="print-action-description">{description}</p>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">{children}</div>
        <footer className="flex flex-col-reverse gap-3 border-t border-line bg-surface px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
          <button className="rounded-md border border-line px-4 py-2.5 text-sm font-bold text-ink disabled:opacity-50" disabled={pending} onClick={onCancel} ref={cancelRef} type="button">{cancelLabel}</button>
          {actions}
        </footer>
      </div>
    </div>
  )
}

function SpoolIdentity({ entry }: { entry: ResolvedPrintJobSpool }) {
  const { t } = useTranslation()
  const spool = entry.spool
  return (
    <div className="min-w-0">
      <h3 className="break-words text-sm font-semibold text-ink">{spoolTitle(entry, t('prints.spoolFallback', { id: entry.link.spool_id }))}</h3>
      <p className="mt-0.5 font-mono text-xs text-ink-muted">{spool?.code ?? t('prints.spoolFallback', { id: entry.link.spool_id })}</p>
      {spool && <p className="mt-2 text-xs text-ink-muted">{spool.manufacturer.name} · {spool.material.name} · {spool.color_name}</p>}
    </div>
  )
}

function StartEntry({ entry }: { entry: ResolvedPrintJobSpool }) {
  const { t } = useTranslation()
  const spool = entry.spool
  const warnings: string[] = []
  if (!spool) warnings.push(t('prints.start.warnings.missing'))
  if (spool?.status === 'LOW') warnings.push(t('prints.start.warnings.low'))
  if (spool?.status === 'EMPTY') warnings.push(t('prints.start.warnings.empty'))
  if (spool?.status === 'ARCHIVED' || spool?.archived_at) warnings.push(t('prints.start.warnings.archived'))
  if (spool?.status === 'IN_USE') warnings.push(t('prints.start.warnings.inUse'))
  if (spool && entry.link.estimated_weight_g != null && Number(entry.link.estimated_weight_g) > Number(spool.current_filament_weight_g)) warnings.push(t('prints.start.warnings.insufficientEstimate'))

  return (
    <li className="rounded-lg border border-line bg-surface-raised p-4">
      <SpoolIdentity entry={entry} />
      <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
        {spool && <div><dt className="text-ink-muted">{t('prints.start.available')}</dt><dd className="mt-0.5 font-semibold text-ink">{formatWeight(Number(spool.current_filament_weight_g))} · {formatPercent(spool.remaining_percent)}</dd></div>}
        <div><dt className="text-ink-muted">{t('prints.start.estimated')}</dt><dd className="mt-0.5 font-semibold text-ink">{entry.link.estimated_weight_g == null ? '—' : formatWeight(Number(entry.link.estimated_weight_g))}</dd></div>
      </dl>
      {warnings.map((warning) => <p className="mt-3 text-sm font-medium text-amber-800 dark:text-amber-200" key={warning} role="status">⚠ {warning}</p>)}
    </li>
  )
}

export function StartPrintDialog(props: DialogBaseProps) {
  const { t } = useTranslation()
  const mutation = useStartPrintJob()
  const blocked = props.entries.some(({ spool }) => !spool || spool.status === 'EMPTY' || spool.status === 'ARCHIVED' || spool.status === 'IN_USE' || Boolean(spool.archived_at))
  const spoolCodes = props.entries.flatMap(({ spool }) => spool ? [spool.code] : [])

  const actions = <button className="w-full rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto" disabled={blocked || mutation.isPending} onClick={() => mutation.mutate({ id: props.printJob.id, spoolCodes }, { onSuccess: props.onSuccess })} type="button">{mutation.isPending ? t('prints.start.pending') : t('prints.start.confirm')}</button>

  return (
    <DialogFrame actions={actions} cancelLabel={t('common.cancel')} description={t('prints.start.description', { count: props.entries.length })} onCancel={props.onCancel} pending={mutation.isPending} title={t('prints.start.title', { name: props.printJob.name })}>
      <p className="mb-4 text-sm font-semibold text-ink">{t('prints.start.spoolsUsed', { count: props.entries.length })}</p>
      <ul className="space-y-3">{props.entries.map((entry) => <StartEntry entry={entry} key={entry.link.spool_id} />)}</ul>
      <p className="mt-5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-6 text-ink">{t('prints.start.inUseNotice')}</p>
      {mutation.error && <p className="mt-4 text-sm font-semibold text-red-600 dark:text-red-400" role="alert">{lifecycleError(mutation.error, 'start', t)}</p>}
    </DialogFrame>
  )
}

function parseConsumption(raw: string): number | null {
  const value = raw.trim()
  if (!value) return null
  if (!/^\d+(?:[.,]\d{1,3})?$/.test(value)) return Number.NaN
  return Number(value.replace(',', '.'))
}

export function FinishPrintDialog(props: DialogBaseProps) {
  const { t } = useTranslation()
  const mutation = useFinishPrintJob()
  const [values, setValues] = useState<Record<number, string>>({})
  const [clientErrors, setClientErrors] = useState<Map<number, string>>(new Map())
  const [submittedPayload, setSubmittedPayload] = useState<PrintJobFinishPayload | null>(null)
  const serverErrors = useMemo(() => submittedPayload ? mapFinishValidationErrors(mutation.error, submittedPayload, t('prints.finish.invalidWeight')) : new Map<number, string>(), [mutation.error, submittedPayload, t])
  const parsedValues = props.entries.map(({ link }) => parseConsumption(values[link.spool_id] ?? ''))
  const hasEmpty = parsedValues.some((value) => value == null)
  const validSum = parsedValues.reduce<number>((sum, value) => sum + (value != null && Number.isFinite(value) ? value : 0), 0)
  const spoolCodes = props.entries.flatMap(({ spool }) => spool ? [spool.code] : [])

  const submit = () => {
    const errors = new Map<number, string>()
    const consumptions: PrintJobFinishPayload['consumptions'] = []
    for (const entry of props.entries) {
      const value = parseConsumption(values[entry.link.spool_id] ?? '')
      if (value == null) continue
      if (!Number.isFinite(value) || value < 0) {
        errors.set(entry.link.spool_id, t('prints.finish.invalidWeight'))
        continue
      }
      if (entry.spool && value > Number(entry.spool.current_filament_weight_g)) {
        errors.set(entry.link.spool_id, t('prints.finish.exceedsAvailable'))
        continue
      }
      consumptions.push({ spool_id: entry.link.spool_id, actual_weight_g: value })
    }
    setClientErrors(errors)
    if (errors.size) return
    const payload = { consumptions }
    setSubmittedPayload(payload)
    mutation.mutate({ id: props.printJob.id, payload, spoolCodes }, { onSuccess: props.onSuccess })
  }

  const actions = <button className="w-full rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto" disabled={mutation.isPending} onClick={submit} type="button">{mutation.isPending ? t('prints.finish.pending') : t('prints.actions.finish')}</button>

  return (
    <DialogFrame actions={actions} cancelLabel={t('common.cancel')} description={t('prints.finish.description')} onCancel={props.onCancel} pending={mutation.isPending} title={t('prints.finish.title')}>
      <p className="mb-5 text-base font-semibold text-ink">{props.printJob.name}</p>
      <div className="space-y-4">{props.entries.map((entry) => {
        const id = entry.link.spool_id
        const error = clientErrors.get(id) ?? serverErrors.get(id)
        const errorId = `consumption-${id}-error`
        return <section className="rounded-lg border border-line bg-surface-raised p-4" key={id}><SpoolIdentity entry={entry} /><dl className="mt-3 grid grid-cols-2 gap-3 text-xs"><div><dt className="text-ink-muted">{t('prints.finish.available')}</dt><dd className="mt-0.5 font-semibold text-ink">{entry.spool ? formatWeight(Number(entry.spool.current_filament_weight_g)) : '—'}</dd></div><div><dt className="text-ink-muted">{t('prints.finish.estimated')}</dt><dd className="mt-0.5 font-semibold text-ink">{entry.link.estimated_weight_g == null ? '—' : formatWeight(Number(entry.link.estimated_weight_g))}</dd></div></dl><label className="mt-4 block text-sm font-semibold text-ink" htmlFor={`consumption-${id}`}>{t('prints.finish.consumed')}<span className="relative mt-1.5 block"><input aria-describedby={error ? errorId : undefined} aria-invalid={Boolean(error)} className="w-full rounded-md border border-line bg-surface px-3 py-2.5 pr-10 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 aria-[invalid=true]:border-red-500" data-spool-id={id} disabled={mutation.isPending} id={`consumption-${id}`} inputMode="decimal" onChange={(event) => { setValues((current) => ({ ...current, [id]: event.target.value })); setClientErrors((current) => { const next = new Map(current); next.delete(id); return next }); mutation.reset() }} placeholder="0" value={values[id] ?? ''} /><span className="absolute inset-y-0 right-3 grid place-items-center text-sm text-ink-muted">g</span></span></label>{error && <p className="mt-2 text-sm font-medium text-red-600 dark:text-red-400" id={errorId} role="alert">{error}</p>}</section>
      })}</div>
      {hasEmpty && <div className="mt-5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-6 text-ink" role="status"><strong>{t('prints.finish.partialWarningTitle')}</strong><p className="mt-1">{t('prints.finish.partialWarning')}</p></div>}
      <p className="mt-5 text-sm font-semibold text-ink">{t(hasEmpty ? 'prints.finish.consumptionSoFar' : 'prints.finish.totalConsumption', { weight: formatWeight(validSum) })}</p>
      {mutation.error && serverErrors.size === 0 && <p className="mt-4 text-sm font-semibold text-red-600 dark:text-red-400" role="alert">{lifecycleError(mutation.error, 'finish', t)}</p>}
    </DialogFrame>
  )
}
