import { AlertTriangle, ArrowRight, Droplets } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { SpoolColorIndicator } from '../spool/SpoolColorIndicator'
import { SpoolStatusBadge } from '../spool/SpoolStatusBadge'
import { formatPercent, formatWeight } from '../../lib/inventory'
import type { Spool } from '../../types/spool'

interface CriticalSpoolsProps {
  spools: readonly Spool[]
}

export function CriticalSpools({ spools }: CriticalSpoolsProps) {
  const { t } = useTranslation()
  return (
    <section
      aria-labelledby="critical-title"
      className="rounded-lg border border-line bg-surface shadow-sm"
    >
      <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400">
            <AlertTriangle
              aria-hidden="true"
              className="size-[1.1rem]"
              strokeWidth={1.8}
            />
          </span>
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold tracking-tight" id="critical-title">
              {t('dashboard.attention')}
            </h2>
            <p className="text-xs text-ink-muted">{t('dashboard.description')}</p>
          </div>
        </div>
        <Link
          className="group flex shrink-0 items-center gap-1.5 rounded-md text-xs font-semibold text-accent focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
          to="/inventory"
        >
          <span className="hidden sm:inline">{t('inventory.title')}</span>
          <span className="sm:hidden">{t('common.appName')}</span>
          <ArrowRight
            aria-hidden="true"
            className="size-3.5 transition-transform group-hover:translate-x-0.5"
          />
        </Link>
      </div>

      {spools.length === 0 ? (
        <div className="px-5 py-8 sm:px-6">
          <p className="text-sm font-medium text-ink">{t('dashboard.criticalEmpty')}</p>
          <p className="mt-1 text-sm text-ink-muted">
            {t('dashboard.criticalEmptyDescription')}
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-line" role="list">
          {spools.map((spool) => (
            <li className="px-5 py-4 sm:px-6" key={spool.id}>
              <article className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                <div className="flex min-w-0 items-start gap-3">
                  <SpoolColorIndicator
                    className="mt-1"
                    colorHex={spool.color_hex}
                    colorName={spool.color_name}
                  />
                  <div className="min-w-0">
                    {spool.display_name ? <><h3 className="truncate text-sm font-semibold text-ink">{spool.display_name}</h3><p className="mt-1 font-mono text-sm font-bold tracking-wide text-ink">{spool.code}</p></> : <h3 className="font-mono text-sm font-bold tracking-wide text-ink">{spool.code}</h3>}
                    <p className="mt-1 truncate text-sm text-ink-muted">
                      {spool.manufacturer.name} {spool.material.name}{' '}
                      <span className="text-ink">{spool.color_name}</span>
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 pl-[1.625rem] sm:justify-end sm:pl-0">
                  <span className="font-mono text-xs font-semibold text-ink-muted">
                    {formatWeight(Number(spool.current_filament_weight_g))}
                  </span>
                  <span className="font-mono text-xs font-semibold text-ink">
                    {formatPercent(spool.remaining_percent)}
                  </span>
                  {(spool.status === 'EMPTY' || spool.status === 'LOW') && (
                    <SpoolStatusBadge status={spool.status} />
                  )}
                  {spool.needs_drying && (
                    <span className="inline-flex items-center gap-1 rounded border border-sky-500/35 bg-sky-500/10 px-2 py-1 font-mono text-[0.62rem] font-bold tracking-[0.08em] text-sky-700 dark:text-sky-300">
                      <Droplets aria-hidden="true" className="size-3" />
                      DRYING
                    </span>
                  )}
                </div>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
