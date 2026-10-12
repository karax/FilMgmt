import { AlertTriangle, RotateCcw, Scale, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { isApiError } from '../../api/client'
import { useCalibrationHistory, useConfirmCalibration, useCreateTareProfile, usePreviewCalibration, useTareProfiles, useUndoCalibration } from '../../hooks/useCalibrations'
import type { CalibrationEvent, CalibrationInput, CalibrationPreview, TareConfidence, TareSource } from '../../types/calibration'
import type { Spool } from '../../types/spool'

type TareMode = 'PROFILE' | 'MANUAL' | 'UNKNOWN'

export function SpoolCalibrationPanel({ spool }: { spool: Spool }) {
  const { i18n, t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [measured, setMeasured] = useState('')
  const [tareMode, setTareMode] = useState<TareMode>('PROFILE')
  const [profileId, setProfileId] = useState<number | null>(null)
  const [tare, setTare] = useState('')
  const [source, setSource] = useState<TareSource>('MANUAL')
  const [confidence, setConfidence] = useState<TareConfidence>('MEDIUM')
  const [note, setNote] = useState('')
  const [previewResult, setPreviewResult] = useState<CalibrationPreview | null>(null)
  const [idempotencyKey, setIdempotencyKey] = useState('')
  const [feedback, setFeedback] = useState<string | null>(null)
  const [newProfile, setNewProfile] = useState({ name: '', tare: '', source: 'KNOWN' as TareSource })
  const profiles = useTareProfiles(open)
  const history = useCalibrationHistory(spool.code, showHistory || open)
  const preview = usePreviewCalibration(spool.code)
  const confirm = useConfirmCalibration(spool.code)
  const undo = useUndoCalibration(spool.code)
  const createProfile = useCreateTareProfile()

  const availableProfiles = Array.isArray(profiles.data) ? profiles.data : []
  const events = Array.isArray(history.data) ? history.data : []
  const lastCalibration = events.find((event) => event.event_type === 'PHYSICAL_CALIBRATION' && !event.reversed_at)

  function resetPreview() {
    setPreviewResult(null)
    setIdempotencyKey('')
    setFeedback(null)
  }

  function payload(): CalibrationInput | null {
    if (!validWeight(measured)) return null
    const base = { measured_total_g: measured, ...(note.trim() ? { note: note.trim() } : {}) }
    if (tareMode === 'PROFILE') return profileId ? { ...base, tare_profile_id: profileId } : null
    if (tareMode === 'MANUAL' && validWeight(tare)) return { ...base, tare_g: tare, tare_source: source, tare_confidence: confidence }
    return null
  }

  async function review() {
    const input = payload()
    if (!input) return
    setFeedback(null)
    try {
      const result = await preview.mutateAsync(input)
      setPreviewResult(result)
      setIdempotencyKey(makeKey())
    } catch (error) {
      setFeedback(calibrationError(error, t))
    }
  }

  async function apply() {
    const input = payload()
    if (!input || !previewResult || !idempotencyKey) return
    setFeedback(null)
    try {
      await confirm.mutateAsync({ ...input, expected_current_remaining_g: String(previewResult.current_remaining_g), idempotency_key: idempotencyKey })
      setFeedback(t('calibration.success'))
      setOpen(false)
      setShowHistory(true)
      setPreviewResult(null)
    } catch (error) {
      const stale = stalePreview(error)
      if (stale) {
        setPreviewResult(stale)
        setIdempotencyKey(makeKey())
      }
      setFeedback(calibrationError(error, t))
    }
  }

  async function addProfile() {
    if (!newProfile.name.trim() || !validWeight(newProfile.tare)) return
    const created = await createProfile.mutateAsync({ name: newProfile.name.trim(), tare_g: newProfile.tare, source: newProfile.source })
    setProfileId(created.id)
    setTareMode('PROFILE')
    setNewProfile({ name: '', tare: '', source: 'KNOWN' })
    resetPreview()
  }

  async function reverse(id: number) {
    const reason = window.prompt(t('calibration.undoPrompt'))?.trim()
    if (!reason) return
    try {
      await undo.mutateAsync({ id, reason })
      setFeedback(t('calibration.undoSuccess'))
    } catch (error) {
      setFeedback(calibrationError(error, t))
    }
  }

  return (
    <section aria-labelledby="calibration-title" className="rounded-lg border border-line bg-surface p-5 shadow-sm lg:col-span-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink" id="calibration-title">{t('calibration.title')}</h2>
          <p className="mt-1 text-sm text-ink-muted">{t('calibration.description')}</p>
        </div>
        <button className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar" onClick={() => { setOpen(true); setFeedback(null) }} type="button"><Scale className="size-4" />{t('calibration.open')}</button>
      </div>
      {lastCalibration && <div className="mt-4 grid gap-3 rounded-md border border-line bg-canvas/40 p-4 sm:grid-cols-3"><Metric label={t('calibration.last')} value={formatDate(lastCalibration.effective_at, i18n.resolvedLanguage)} /><Metric label={t('calibration.physicalRemaining')} value={`${formatWeight(lastCalibration.calculated_filament_g)} g`} /><Metric label={t('calibration.tare')} value={`${formatWeight(lastCalibration.tare_g_used)} g · ${lastCalibration.tare_source_used}`} /></div>}
      {feedback && <p className="mt-4 rounded-md border border-line px-4 py-3 text-sm text-ink" role="status">{feedback}</p>}
      <button className="mt-4 text-sm font-semibold text-accent underline underline-offset-4" onClick={() => setShowHistory((value) => !value)} type="button">{showHistory ? t('calibration.hideHistory') : t('calibration.showHistory')}</button>
      {showHistory && <CalibrationHistory events={events} onUndo={reverse} pending={undo.isPending} />}

      {open && <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-black/55 p-4" role="presentation"><div aria-labelledby="calibration-dialog-title" aria-modal="true" className="my-6 w-full max-w-2xl rounded-lg border border-line bg-surface p-5 shadow-xl" role="dialog">
        <div className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold text-ink" id="calibration-dialog-title">{t('calibration.open')}</h2><p className="mt-1 text-sm text-ink-muted">{spool.code} · {spool.manufacturer.name} {spool.material.name} {spool.color_name}</p></div><button aria-label={t('common.cancel')} onClick={() => setOpen(false)} type="button"><X className="size-5" /></button></div>
        <div className="mt-5 rounded-md border border-line bg-canvas/40 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{t('calibration.currentSystem')}</p><p className="mt-1 font-mono text-xl font-bold text-ink">{formatWeight(spool.current_filament_weight_g)} g</p></div>
        <label className="mt-5 block text-sm font-semibold text-ink">{t('calibration.measuredTotal')}<div className="relative mt-1.5"><input autoFocus className="w-full rounded-md border border-line bg-surface px-3 py-2.5 pr-9" min="0" onChange={(event) => { setMeasured(event.target.value); resetPreview() }} placeholder="637.000" step="0.001" type="number" value={measured} /><span className="absolute right-3 top-2.5 text-ink-muted">g</span></div><span className="mt-1 block text-xs font-normal text-ink-muted">{t('calibration.measuredHelp')}</span></label>
        <fieldset className="mt-5"><legend className="text-sm font-semibold text-ink">{t('calibration.emptyWeight')}</legend><div className="mt-2 space-y-2">{(['PROFILE', 'MANUAL', 'UNKNOWN'] as TareMode[]).map((mode) => <label className="flex items-start gap-2 rounded-md border border-line p-3 text-sm text-ink" key={mode}><input checked={tareMode === mode} className="mt-0.5 accent-[var(--accent)]" name="tare-mode" onChange={() => { setTareMode(mode); resetPreview() }} type="radio" />{t(`calibration.tareMode.${mode}`)}</label>)}</div></fieldset>
        {tareMode === 'PROFILE' && <div className="mt-3"><select aria-label={t('calibration.profile')} className="w-full rounded-md border border-line bg-surface px-3 py-2.5" onChange={(event) => { setProfileId(event.target.value ? Number(event.target.value) : null); resetPreview() }} value={profileId ?? ''}><option value="">{t('calibration.chooseProfile')}</option>{availableProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name} — {formatWeight(profile.tare_g)} g · {profile.source}/{profile.confidence}</option>)}</select><details className="mt-3 rounded-md border border-line p-3"><summary className="cursor-pointer text-sm font-semibold text-accent">{t('calibration.createProfile')}</summary><div className="mt-3 grid gap-2 sm:grid-cols-2"><input aria-label={t('calibration.profileName')} className="rounded-md border border-line bg-surface px-3 py-2" onChange={(event) => setNewProfile((value) => ({ ...value, name: event.target.value }))} placeholder={t('calibration.profileName')} value={newProfile.name} /><input aria-label={t('calibration.tare')} className="rounded-md border border-line bg-surface px-3 py-2" min="0" onChange={(event) => setNewProfile((value) => ({ ...value, tare: event.target.value }))} placeholder="224.000" step="0.001" type="number" value={newProfile.tare} /><select aria-label={t('calibration.source')} className="rounded-md border border-line bg-surface px-3 py-2" onChange={(event) => setNewProfile((value) => ({ ...value, source: event.target.value as TareSource }))} value={newProfile.source}>{(['MEASURED', 'KNOWN', 'ESTIMATED', 'MANUAL'] as TareSource[]).map((item) => <option key={item}>{item}</option>)}</select><button className="rounded-md border border-accent px-3 py-2 font-semibold text-accent disabled:opacity-50" disabled={!newProfile.name.trim() || !validWeight(newProfile.tare) || createProfile.isPending} onClick={() => void addProfile()} type="button">{t('calibration.saveProfile')}</button></div></details></div>}
        {tareMode === 'MANUAL' && <div className="mt-3 grid gap-3 sm:grid-cols-3"><label className="text-sm font-medium text-ink">{t('calibration.tare')}<input className="mt-1.5 w-full rounded-md border border-line bg-surface px-3 py-2.5" min="0" onChange={(event) => { setTare(event.target.value); resetPreview() }} step="0.001" type="number" value={tare} /></label><label className="text-sm font-medium text-ink">{t('calibration.source')}<select className="mt-1.5 w-full rounded-md border border-line bg-surface px-3 py-2.5" onChange={(event) => { setSource(event.target.value as TareSource); resetPreview() }} value={source}>{(['MEASURED', 'KNOWN', 'ESTIMATED', 'MANUAL'] as TareSource[]).map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-sm font-medium text-ink">{t('calibration.confidence')}<select className="mt-1.5 w-full rounded-md border border-line bg-surface px-3 py-2.5" onChange={(event) => { setConfidence(event.target.value as TareConfidence); resetPreview() }} value={confidence}>{(['HIGH', 'MEDIUM', 'LOW'] as TareConfidence[]).map((item) => <option key={item}>{item}</option>)}</select></label></div>}
        {tareMode === 'UNKNOWN' && <div className="mt-3 flex gap-3 rounded-md border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-ink"><AlertTriangle className="size-5 shrink-0 text-amber-600" /><p>{t('calibration.unknownHelp')}</p></div>}
        <label className="mt-4 block text-sm font-medium text-ink">{t('calibration.note')}<input className="mt-1.5 w-full rounded-md border border-line bg-surface px-3 py-2.5" maxLength={500} onChange={(event) => { setNote(event.target.value); resetPreview() }} value={note} /></label>
        {previewResult && <Preview result={previewResult} />}
        {feedback && <p className="mt-4 text-sm text-red-600" role="alert">{feedback}</p>}
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end"><button className="rounded-md border border-line px-4 py-2.5 font-semibold text-ink" onClick={() => setOpen(false)} type="button">{t('common.cancel')}</button>{previewResult ? <button className="rounded-md bg-accent px-4 py-2.5 font-bold text-sidebar disabled:opacity-50" disabled={confirm.isPending} onClick={() => void apply()} type="button">{confirm.isPending ? t('calibration.confirming') : t('calibration.confirm')}</button> : <button className="rounded-md bg-accent px-4 py-2.5 font-bold text-sidebar disabled:opacity-50" disabled={!payload() || preview.isPending} onClick={() => void review()} type="button">{preview.isPending ? t('calibration.reviewing') : t('calibration.review')}</button>}</div>
      </div></div>}
    </section>
  )
}

function Preview({ result }: { result: CalibrationPreview }) {
  const { t } = useTranslation()
  return <div className="mt-5 rounded-md border border-accent/40 bg-accent-soft/20 p-4"><div className="space-y-2"><PreviewRow label={t('calibration.measuredTotal')} value={result.measured_total_g} /><PreviewRow label={t('calibration.tare')} value={result.tare_g} /><div className="border-t border-line pt-2"><PreviewRow label={t('calibration.physicalRemaining')} value={result.calculated_filament_g} /></div><PreviewRow label={t('calibration.currentSystem')} value={result.current_remaining_g} /><PreviewRow label={t('calibration.adjustment')} signed value={result.adjustment_g} /></div>{result.is_estimated && <p className="mt-3 rounded bg-amber-500/10 p-2 text-sm text-amber-800 dark:text-amber-200">{t('calibration.estimatedWarning')}</p>}{result.unreconciled_prints.length > 0 && <div className="mt-3 rounded bg-amber-500/10 p-3 text-sm text-ink"><p className="font-semibold">{t('calibration.pendingWarning', { count: result.unreconciled_prints.length })}</p><p className="mt-1 text-ink-muted">{t('calibration.pendingWarningHelp')}</p></div>}</div>
}

function PreviewRow({ label, signed, value }: { label: string; signed?: boolean; value: string | number }) { const number = Number(value); return <div className="flex justify-between gap-4 text-sm"><span className="text-ink-muted">{label}</span><strong className="font-mono text-ink">{signed && number > 0 ? '+' : ''}{formatWeight(value)} g</strong></div> }
function Metric({ label, value }: { label: string; value: string }) { return <div><dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</dt><dd className="mt-1 text-sm font-semibold text-ink">{value}</dd></div> }

function CalibrationHistory({ events, onUndo, pending }: { events: CalibrationEvent[]; onUndo: (id: number) => Promise<void>; pending: boolean }) {
  const { i18n, t } = useTranslation()
  if (!events.length) return <p className="mt-4 text-sm text-ink-muted">{t('calibration.noHistory')}</p>
  const undoableId = events[0]?.event_type === 'PHYSICAL_CALIBRATION' && !events[0].reversed_at ? events[0].id : null
  return <ol className="mt-4 space-y-3">{events.map((event) => <li className="rounded-md border border-line bg-canvas/30 p-4" key={event.id}><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold text-ink">{event.event_type === 'REVERSAL' ? t('calibration.reversal') : t('calibration.physicalEvent')}</p><p className="mt-1 text-xs text-ink-muted">{formatDate(event.created_at, i18n.resolvedLanguage)}</p></div><strong className="font-mono text-ink">{Number(event.adjustment_g) > 0 ? '+' : ''}{formatWeight(event.adjustment_g)} g</strong></div>{event.event_type === 'PHYSICAL_CALIBRATION' && <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-4"><Metric label={t('calibration.measuredTotal')} value={`${formatWeight(event.measured_total_g)} g`} /><Metric label={t('calibration.tare')} value={`${formatWeight(event.tare_g_used)} g`} /><Metric label={t('calibration.expectedBefore')} value={`${formatWeight(event.previous_remaining_g)} g`} /><Metric label={t('calibration.drift')} value={`${formatWeight(event.adjustment_g)} g`} /></dl>}{event.note && <p className="mt-3 text-sm text-ink-muted">{event.note}</p>}{event.id === undoableId && <button className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-accent" disabled={pending} onClick={() => void onUndo(event.id)} type="button"><RotateCcw className="size-4" />{t('calibration.undo')}</button>}</li>)}</ol>
}

function validWeight(value: string): boolean { return /^\d+(?:\.\d{1,3})?$/.test(value) && Number(value) >= 0 }
function formatWeight(value: string | number | null): string { if (value == null) return '—'; const number = Number(value); return Number.isFinite(number) ? number.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 3 }) : String(value) }
function formatDate(value: string, language?: string): string { return new Intl.DateTimeFormat(language === 'en' ? 'en' : 'pt-BR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) }
function makeKey(): string { return globalThis.crypto?.randomUUID?.() ?? `cal-${Date.now()}-${Math.random().toString(16).slice(2)}` }
function stalePreview(error: unknown): CalibrationPreview | null { if (!isApiError(error) || error.status !== 409 || typeof error.detail !== 'object' || error.detail === null) return null; const detail = (error.detail as { detail?: { code?: string; preview?: CalibrationPreview } }).detail; return detail?.code === 'stale_calibration_preview' && detail.preview ? detail.preview : null }
function calibrationError(error: unknown, t: (key: string) => string): string { if (stalePreview(error)) return t('calibration.errors.stale'); if (isApiError(error) && error.status === 422) return t('calibration.errors.validation'); if (isApiError(error) && error.status === 409) return t('calibration.errors.conflict'); return t('calibration.errors.generic') }
