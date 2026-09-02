import { Droplets } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { formatWeight } from '../../lib/inventory'
import type { Spool } from '../../types/spool'
import { SpoolColorIndicator } from './SpoolColorIndicator'
import { SpoolProgressBar } from './SpoolProgressBar'
import { SpoolStatusBadge } from './SpoolStatusBadge'

interface SpoolCardProps {
  spool: Spool
  compact?: boolean
  onClick?: () => void
}

export function SpoolCard({
  spool,
  compact = false,
  onClick,
}: SpoolCardProps) {
  const { t } = useTranslation()
  const content = (
    <SpoolCardContent compact={compact} interactive={Boolean(onClick)} spool={spool} />
  )
  const classes = `flex h-full w-full min-h-72 flex-col rounded-lg border border-line bg-surface p-5 text-left shadow-sm transition-colors ${
    onClick
      ? 'cursor-pointer hover:border-accent/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent'
      : ''
  } ${compact ? 'min-h-0 gap-0 p-4' : ''}`

  if (onClick) {
    return (
      <button
        aria-label={t('spool.view', { code: spool.code })}
        className={classes}
        onClick={onClick}
        type="button"
      >
        {content}
      </button>
    )
  }

  return <article className={classes}>{content}</article>
}

interface SpoolCardContentProps {
  spool: Spool
  compact: boolean
  interactive: boolean
}

function SpoolCardContent({
  spool,
  compact,
  interactive,
}: SpoolCardContentProps) {
  const { t } = useTranslation()
  return (
    <>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          {spool.display_name && <p className="truncate text-base font-semibold text-ink">{spool.display_name}</p>}
          <p className={`${spool.display_name ? 'mt-1' : ''} truncate text-sm font-semibold text-ink`}>
            <span>{spool.manufacturer.name}</span>{' '}
            <span className="text-ink-muted">{spool.material.name}</span>
          </p>
          <CardCode code={spool.code} interactive={interactive} />
        </div>
        <SpoolStatusBadge status={spool.status} />
      </div>

      <div className="mt-5 min-w-0">
        <p className="flex items-center gap-2 text-sm text-ink">
          <SpoolColorIndicator colorHex={spool.color_hex} colorName={spool.color_name} />
          <span>{spool.color_name}</span>
        </p>
        {!compact && spool.product_name && (
          <p className="mt-1 truncate text-sm text-ink-muted">{spool.product_name}</p>
        )}
      </div>

      <div className="mt-6">
        <SpoolProgressBar
          label={spool.code}
          remainingPercent={spool.remaining_percent}
        />
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-base font-semibold tracking-tight text-ink">
          {formatWeight(Number(spool.current_filament_weight_g))}
          {!compact && (
            <span className="font-normal text-ink-muted">
              {' '}/ {formatWeight(Number(spool.initial_filament_weight_g))}
            </span>
          )}
        </p>
        {spool.needs_drying && (
          <span className="inline-flex shrink-0 items-center gap-1 rounded border border-sky-500/35 bg-sky-500/10 px-2 py-1 text-xs font-semibold text-sky-700 dark:text-sky-300">
            <Droplets aria-hidden="true" className="size-3" />
            {t('spool.needsDrying')}
          </span>
        )}
      </div>

    </>
  )
}

function CardCode({ code, interactive }: { code: string; interactive: boolean }) {
  const content: ReactNode = code

  if (interactive) {
    return <span className="mt-2 block font-mono text-xs tracking-[0.1em] text-ink-muted">{content}</span>
  }

  return (
    <h3 className="mt-2 font-mono text-xs font-bold tracking-[0.1em] text-ink-muted">
      {content}
    </h3>
  )
}
