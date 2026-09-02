import { AlertCircle, Archive, Pencil, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../api/client'
import { SpoolDetailsHeader } from '../components/spool/SpoolDetailsHeader'
import { InfoRow, SpoolInfoSection } from '../components/spool/SpoolInfoSection'
import { SpoolPrintSettings } from '../components/spool/SpoolPrintSettings'
import { SpoolQrCard } from '../components/spool/SpoolQrCard'
import { SpoolWeightPanel } from '../components/spool/SpoolWeightPanel'
import { useSpool } from '../hooks/useSpool'
import { useArchiveSpool, useDeleteSpool } from '../hooks/useSpoolMutations'
import { formatCurrency, formatDate } from '../lib/inventory'

export function SpoolDetailsPage() {
  const { code } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { data: spool, error, isFetching, isPending, refetch } = useSpool(code)
  const archive = useArchiveSpool()
  const remove = useDeleteSpool()
  const [dialog, setDialog] = useState<'archive' | 'delete' | null>(null)
  const [confirmation, setConfirmation] = useState('')
  const [feedback, setFeedback] = useState<string | null>(() => (location.state as { feedback?: string } | null)?.feedback ?? null)

  if (isPending) return <SpoolDetailsSkeleton />

  if (error) {
    if (error instanceof ApiError && error.status === 404) return <SpoolNotFound />
    return <SpoolLoadError isFetching={isFetching} onRetry={() => void refetch()} />
  }

  if (!spool) return <SpoolNotFound />

  const archived = spool.status === 'ARCHIVED'
  const canArchive = !archived && spool.status !== 'IN_USE'
  const mutationError = archive.error ?? remove.error

  return (
    <main aria-labelledby="spool-details-title">
      <SpoolDetailsHeader spool={spool} />
      {feedback && <div className="mt-5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-ink" role="status">{feedback}</div>}
      {mutationError && <div className="mt-5 rounded-md border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-ink" role="alert">{mutationMessage(mutationError)}</div>}
      <section aria-label="Spool actions" className="mt-6 flex flex-wrap gap-3">
        <Link className="inline-flex items-center gap-2 rounded-md border border-line bg-surface px-4 py-2.5 text-sm font-bold text-ink transition-colors hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" to={`/spools/${encodeURIComponent(spool.code)}/edit`}><Pencil aria-hidden="true" className="size-4" />Edit Spool</Link>
        {canArchive && <button className="inline-flex items-center gap-2 rounded-md border border-amber-500/40 bg-surface px-4 py-2.5 text-sm font-bold text-ink transition-colors hover:bg-amber-500/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onClick={() => setDialog('archive')} type="button"><Archive aria-hidden="true" className="size-4" />Archive Spool</button>}
      </section>
      <div className="mt-8 grid items-start gap-5 lg:grid-cols-2">
        <SpoolWeightPanel spool={spool} />
        <SpoolPrintSettings spool={spool} />
        <SpoolInfoSection title="Basic Information">
          <InfoRow label="Manufacturer">
            {spool.manufacturer.website ? <a className="text-accent underline underline-offset-4" href={spool.manufacturer.website} rel="noopener noreferrer" target="_blank">{spool.manufacturer.name}</a> : spool.manufacturer.name}
          </InfoRow>
          <InfoRow label="Material">{spool.material.name}{spool.material.category && spool.material.category !== spool.material.name ? ` · ${spool.material.category}` : ''}</InfoRow>
          <InfoRow label="Color">{spool.color_name}</InfoRow>
          <InfoRow label="Status">{spool.status}</InfoRow>
        </SpoolInfoSection>
        <SpoolQrCard code={spool.code} displayName={spool.display_name} />
        <SpoolInfoSection title="Purchase">
          <InfoRow label="Store name">{spool.store_name ?? '—'}</InfoRow>
          <InfoRow label="Purchase price">{spool.purchase_price == null ? '—' : formatCurrency(spool.purchase_price, spool.currency)}</InfoRow>
          <InfoRow label="Purchase date">{dateOrDash(spool.purchase_date)}</InfoRow>
        </SpoolInfoSection>
        <SpoolInfoSection title="Dates">
          <InfoRow label="Opened at">{dateOrDash(spool.opened_at)}</InfoRow>
          <InfoRow label="Last used at">{dateOrDash(spool.last_used_at)}</InfoRow>
          <InfoRow label="Last dried at">{dateOrDash(spool.last_dried_at)}</InfoRow>
          <InfoRow label="Created at">{dateOrDash(spool.created_at)}</InfoRow>
          <InfoRow label="Updated at">{dateOrDash(spool.updated_at)}</InfoRow>
          {spool.archived_at && <InfoRow label="Archived at">{dateOrDash(spool.archived_at)}</InfoRow>}
        </SpoolInfoSection>
        {spool.notes && <SpoolInfoSection title="Notes"><InfoRow label="Notes">{spool.notes}</InfoRow></SpoolInfoSection>}
      </div>
      <section aria-labelledby="danger-zone-title" className="mt-8 rounded-lg border border-red-500/30 bg-red-500/5 p-5">
        <h2 className="text-base font-semibold text-ink" id="danger-zone-title">Danger Zone</h2>
        {archived ? <><p className="mt-2 text-sm text-ink-muted">This archived spool can be permanently removed if it has no protected history.</p><button className="mt-4 inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2.5 text-sm font-bold text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600" onClick={() => { setConfirmation(''); setDialog('delete') }} type="button"><Trash2 aria-hidden="true" className="size-4" />Delete Spool</button></> : <p className="mt-2 text-sm text-ink-muted">Archive removes a spool from active inventory while preserving its history. Permanent deletion is available only after archival.</p>}
        {spool.status === 'IN_USE' && <p className="mt-2 text-sm text-amber-800 dark:text-amber-200">This spool cannot be archived while a print is in progress.</p>}
      </section>
      {dialog === 'archive' && <ConfirmDialog title={`Archive ${spool.code}?`} description="This spool will be removed from active inventory, but its historical data will be preserved." confirmLabel="Archive Spool" pending={archive.isPending} onCancel={() => setDialog(null)} onConfirm={() => archive.mutate(spool.code, { onSuccess: () => { setDialog(null); setFeedback('Spool archived successfully.') } })} />}
      {dialog === 'delete' && <ConfirmDialog title={`Permanently delete ${spool.code}?`} description="This action cannot be undone. The spool will be permanently removed from the database." confirmLabel="Delete Permanently" pending={remove.isPending} confirmationCode={spool.code} confirmationValue={confirmation} onConfirmationChange={setConfirmation} onCancel={() => setDialog(null)} onConfirm={() => remove.mutate(spool.code, { onSuccess: () => navigate('/inventory', { replace: true, state: { feedback: `${spool.code} was permanently deleted.` } }) })} />}
    </main>
  )
}

function mutationMessage(error: unknown): string {
  if (error instanceof ApiError && typeof error.detail === 'object' && error.detail && 'detail' in error.detail && typeof error.detail.detail === 'string') return error.detail.detail
  if (error instanceof ApiError && error.status === 409) return 'This spool cannot be deleted because it has associated history.'
  return 'Unable to complete this spool action. Please try again.'
}

function ConfirmDialog({ title, description, confirmLabel, pending, confirmationCode, confirmationValue, onConfirmationChange, onCancel, onConfirm }: { title: string; description: string; confirmLabel: string; pending: boolean; confirmationCode?: string; confirmationValue?: string; onConfirmationChange?: (value: string) => void; onCancel: () => void; onConfirm: () => void }) {
  useEffect(() => { const escape = (event: KeyboardEvent) => { if (event.key === 'Escape' && !pending) onCancel() }; window.addEventListener('keydown', escape); return () => window.removeEventListener('keydown', escape) }, [onCancel, pending])
  const confirmed = !confirmationCode || confirmationValue === confirmationCode
  return <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" role="presentation"><div aria-describedby="spool-action-description" aria-labelledby="spool-action-title" aria-modal="true" className="w-full max-w-md rounded-lg border border-line bg-surface p-5 shadow-xl" role="dialog"><h2 className="text-lg font-semibold text-ink" id="spool-action-title">{title}</h2><p className="mt-2 text-sm leading-6 text-ink-muted" id="spool-action-description">{description}</p>{confirmationCode && <label className="mt-5 block text-sm font-semibold text-ink">Type {confirmationCode} to confirm<input autoFocus className="mt-1.5 w-full rounded-md border border-line bg-surface-raised px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent/20" onChange={(event) => onConfirmationChange?.(event.target.value)} value={confirmationValue} /></label>}<div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end"><button className="rounded-md border border-line px-4 py-2.5 text-sm font-bold text-ink" disabled={pending} onClick={onCancel} type="button">Cancel</button><button className="rounded-md bg-red-600 px-4 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50" disabled={pending || !confirmed} onClick={onConfirm} type="button">{pending ? 'Working…' : confirmLabel}</button></div></div></div>
}

function dateOrDash(value: string | null) { return value ? formatDate(value) : '—' }

function SpoolDetailsSkeleton() {
  return <main aria-busy="true" aria-label="Loading spool details" role="status"><div className="h-5 w-36 animate-pulse rounded bg-line" /><div className="mt-6 h-12 w-44 animate-pulse rounded bg-line" /><div className="mt-8 grid gap-5 lg:grid-cols-2">{Array.from({ length: 6 }, (_, index) => <div className="h-52 animate-pulse rounded-lg border border-line bg-surface" key={index} />)}</div></main>
}

function SpoolNotFound() {
  return <main className="rounded-lg border border-line bg-surface px-5 py-12 text-center shadow-sm" aria-labelledby="not-found-title"><h1 id="not-found-title" className="text-xl font-semibold text-ink">Spool not found.</h1><p className="mt-2 text-sm text-ink-muted">The spool may have been removed or the code is invalid.</p><BackButton /></main>
}

function SpoolLoadError({ isFetching, onRetry }: { isFetching: boolean; onRetry: () => void }) {
  return <main className="rounded-lg border border-red-500/30 bg-surface px-5 py-12 text-center shadow-sm" role="alert"><AlertCircle aria-hidden="true" className="mx-auto size-6 text-red-600 dark:text-red-400" /><h1 className="mt-4 text-xl font-semibold text-ink">Unable to load spool.</h1><button className="mt-6 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60" disabled={isFetching} onClick={onRetry} type="button">{isFetching ? 'Retrying…' : 'Retry'}</button></main>
}

function BackButton() { return <Link className="mt-6 inline-flex rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" to="/inventory">Back to Inventory</Link> }
