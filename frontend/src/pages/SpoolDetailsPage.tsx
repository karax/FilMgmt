import { AlertCircle } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '../api/client'
import { SpoolDetailsHeader } from '../components/spool/SpoolDetailsHeader'
import { InfoRow, SpoolInfoSection } from '../components/spool/SpoolInfoSection'
import { SpoolPrintSettings } from '../components/spool/SpoolPrintSettings'
import { SpoolWeightPanel } from '../components/spool/SpoolWeightPanel'
import { useSpool } from '../hooks/useSpool'
import { formatCurrency, formatDate } from '../lib/inventory'

export function SpoolDetailsPage() {
  const { code } = useParams()
  const { data: spool, error, isFetching, isPending, refetch } = useSpool(code)

  if (isPending) return <SpoolDetailsSkeleton />

  if (error) {
    if (error instanceof ApiError && error.status === 404) return <SpoolNotFound />
    return <SpoolLoadError isFetching={isFetching} onRetry={() => void refetch()} />
  }

  if (!spool) return <SpoolNotFound />

  return (
    <main aria-labelledby="spool-details-title">
      <SpoolDetailsHeader spool={spool} />
      <div className="mt-8 grid items-start gap-5 lg:grid-cols-2">
        <SpoolWeightPanel spool={spool} />
        <SpoolInfoSection title="Basic Information">
          <InfoRow label="Manufacturer">
            {spool.manufacturer.website ? <a className="text-accent underline underline-offset-4" href={spool.manufacturer.website} rel="noopener noreferrer" target="_blank">{spool.manufacturer.name}</a> : spool.manufacturer.name}
          </InfoRow>
          <InfoRow label="Material">{spool.material.name}{spool.material.category && spool.material.category !== spool.material.name ? ` · ${spool.material.category}` : ''}</InfoRow>
          <InfoRow label="Color">{spool.color_name}</InfoRow>
          <InfoRow label="Status">{spool.status}</InfoRow>
        </SpoolInfoSection>
        <SpoolInfoSection title="Storage"><InfoRow label="Location">{spool.location?.name ?? 'Unassigned'}</InfoRow></SpoolInfoSection>
        <SpoolInfoSection title="Purchase">
          <InfoRow label="Purchase price">{spool.purchase_price == null ? '—' : formatCurrency(spool.purchase_price, spool.currency)}</InfoRow>
          <InfoRow label="Purchase date">{dateOrDash(spool.purchase_date)}</InfoRow>
        </SpoolInfoSection>
        <SpoolPrintSettings spool={spool} />
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
    </main>
  )
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
