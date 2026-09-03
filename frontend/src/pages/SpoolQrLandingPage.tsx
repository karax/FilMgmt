import {
  AlertCircle,
  ArrowLeft,
  Droplets,
  MapPin,
  PackageOpen,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { isApiError } from '../api/client'
import { SpoolColorIndicator } from '../components/spool/SpoolColorIndicator'
import { SpoolProgressBar } from '../components/spool/SpoolProgressBar'
import { SpoolStatusBadge } from '../components/spool/SpoolStatusBadge'
import { useSpool } from '../hooks/useSpool'
import { formatWeight } from '../lib/inventory'
import { isValidSpoolCode } from '../lib/spoolQr'
import type { Spool } from '../types/spool'

export function SpoolQrLandingPage() {
  const { t } = useTranslation()
  const { code } = useParams()
  const validCode = isValidSpoolCode(code) ? code : undefined
  const { data: spool, error, isFetching, isPending, refetch } = useSpool(validCode)

  if (!validCode) {
    return <QrMessageState title={t('qr.spool.invalid')} />
  }

  if (isPending) return <SpoolQrLandingSkeleton />

  if (error) {
    if (isApiError(error) && error.status === 404) {
      return <QrMessageState title={t('qr.spool.notFound')} />
    }

    return (
      <QrMessageState
        isFetching={isFetching}
        onRetry={() => void refetch()}
        title={t('qr.spool.loadError')}
      />
    )
  }

  if (!spool) return <QrMessageState title={t('qr.spool.notFound')} />

  return <SpoolQrSummary spool={spool} />
}

function SpoolQrSummary({ spool }: { spool: Spool }) {
  const { t } = useTranslation()
  const title = spool.display_name ?? spool.code
  const remainingPercent = optionalNumber(spool.remaining_percent)

  return (
    <article aria-labelledby="qr-spool-title" className="mx-auto w-full max-w-2xl pb-4">
      <Link
        className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 text-sm font-semibold text-ink-muted transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        to="/inventory"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        {t('qr.spool.back')}
      </Link>

      <header className="mt-5 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-accent">
            {t('qr.spool.quickView')}
          </p>
          <h1 className="mt-2 break-words text-2xl font-semibold tracking-tight text-ink sm:text-3xl" id="qr-spool-title">
            {title}
          </h1>
          {spool.display_name && (
            <p className="mt-2 font-mono text-sm font-bold tracking-[0.12em] text-ink-muted">
              {spool.code}
            </p>
          )}
        </div>
        <SpoolStatusBadge status={spool.status} />
      </header>

      <SpoolAlerts spool={spool} />

      <section
        aria-labelledby="current-weight-title"
        className="mt-6 rounded-xl border border-line bg-surface p-5 shadow-sm sm:p-6"
      >
        <h2 className="text-sm font-semibold text-ink-muted" id="current-weight-title">
          {t('qr.spool.currentWeight')}
        </h2>
        <p className="mt-2 text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          {formatOptionalWeight(spool.current_filament_weight_g)}
        </p>
        <div className="mt-6">
          {remainingPercent == null ? (
            <div className="flex items-end justify-between gap-4">
              <span className="font-mono text-xs font-semibold uppercase tracking-[0.1em] text-ink-muted">
                {t('qr.spool.remaining')}
              </span>
              <span className="font-mono text-sm font-semibold text-ink">—</span>
            </div>
          ) : (
            <SpoolProgressBar
              accessibleLabel={t('qr.spool.remainingAria', { code: spool.code })}
              label={spool.code}
              remainingLabel={t('qr.spool.remaining')}
              remainingPercent={remainingPercent}
            />
          )}
        </div>
      </section>

      <dl className="mt-5 grid gap-3 sm:grid-cols-2" data-layout="qr-summary-grid">
        <QuickFact label={t('qr.spool.material')} value={spool.material?.name} />
        <QuickFact label={t('qr.spool.manufacturer')} value={spool.manufacturer?.name} />
        <div className="rounded-lg border border-line bg-surface p-4 shadow-sm sm:col-span-2">
          <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-ink-muted">
            {t('qr.spool.color')}
          </dt>
          <dd className="mt-2 flex min-w-0 items-center gap-2 text-base font-semibold text-ink">
            <SpoolColorIndicator colorHex={spool.color_hex} colorName={spool.color_name} />
            <span className="break-words">{spool.color_name || '—'}</span>
          </dd>
        </div>
        <div className="rounded-lg border border-line bg-surface p-4 shadow-sm sm:col-span-2">
          <dt className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.08em] text-ink-muted">
            <MapPin aria-hidden="true" className="size-4" />
            {t('qr.spool.location')}
          </dt>
          <dd className="mt-2 break-words text-base font-semibold text-ink">
            {spool.location?.name ?? '—'}
          </dd>
        </div>
      </dl>

      <Link
        className="mt-6 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-accent px-5 py-3 text-center text-sm font-bold text-sidebar shadow-sm transition-[filter] hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        to={`/spools/${encodeURIComponent(spool.code)}`}
      >
        <PackageOpen aria-hidden="true" className="size-5" />
        {t('qr.spool.fullDetails')}
      </Link>
    </article>
  )
}

function SpoolAlerts({ spool }: { spool: Spool }) {
  const { t } = useTranslation()
  if (spool.status !== 'LOW' && !spool.needs_drying) return null

  return (
    <div className="mt-5 grid gap-3" aria-label={t('qr.spool.alerts')}>
      {spool.status === 'LOW' && (
        <div className="flex items-center gap-3 rounded-lg border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm font-semibold text-amber-800 dark:text-amber-200" role="status">
          <AlertCircle aria-hidden="true" className="size-5 shrink-0" />
          {t('qr.spool.low')}
        </div>
      )}
      {spool.needs_drying && (
        <div className="flex items-center gap-3 rounded-lg border border-sky-500/35 bg-sky-500/10 px-4 py-3 text-sm font-semibold text-sky-800 dark:text-sky-200" role="status">
          <Droplets aria-hidden="true" className="size-5 shrink-0" />
          {t('qr.spool.needsDrying')}
        </div>
      )}
    </div>
  )
}

function QuickFact({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="min-w-0 rounded-lg border border-line bg-surface p-4 shadow-sm">
      <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-ink-muted">{label}</dt>
      <dd className="mt-2 break-words text-base font-semibold text-ink">{value || '—'}</dd>
    </div>
  )
}

function QrMessageState({
  isFetching = false,
  onRetry,
  title,
}: {
  isFetching?: boolean
  onRetry?: () => void
  title: string
}) {
  const { t } = useTranslation()
  return (
    <section className="mx-auto w-full max-w-2xl rounded-xl border border-line bg-surface px-5 py-12 text-center shadow-sm" role={onRetry ? 'alert' : undefined}>
      <AlertCircle aria-hidden="true" className="mx-auto size-7 text-ink-muted" />
      <h1 className="mt-4 text-xl font-semibold text-ink">{title}</h1>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
        {onRetry && (
          <button
            className="inline-flex min-h-11 items-center justify-center rounded-md bg-accent px-5 py-2.5 text-sm font-bold text-sidebar disabled:opacity-60"
            disabled={isFetching}
            onClick={onRetry}
            type="button"
          >
            {isFetching ? t('qr.spool.retrying') : t('qr.spool.retry')}
          </button>
        )}
        <Link className="inline-flex min-h-11 items-center justify-center rounded-md border border-line px-5 py-2.5 text-sm font-bold text-ink" to="/inventory">
          {t('qr.spool.back')}
        </Link>
      </div>
    </section>
  )
}

function SpoolQrLandingSkeleton() {
  const { t } = useTranslation()
  return (
    <section aria-busy="true" aria-label={t('qr.spool.loading')} className="mx-auto w-full max-w-2xl" role="status">
      <div className="h-11 w-40 animate-pulse rounded bg-line" />
      <div className="mt-5 h-24 animate-pulse rounded-lg bg-line" />
      <div className="mt-6 h-56 animate-pulse rounded-xl border border-line bg-surface" />
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className="h-24 animate-pulse rounded-lg bg-line" />
        <div className="h-24 animate-pulse rounded-lg bg-line" />
        <div className="h-24 animate-pulse rounded-lg bg-line sm:col-span-2" />
      </div>
    </section>
  )
}

function optionalNumber(value: unknown): number | null {
  if (value == null || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatOptionalWeight(value: unknown): string {
  const weight = optionalNumber(value)
  return weight == null ? '—' : formatWeight(weight)
}
