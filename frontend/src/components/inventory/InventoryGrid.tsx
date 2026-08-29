import { MapPin } from 'lucide-react'

import { formatPercent, formatWeight } from '../../lib/inventory'
import type { Spool } from '../../types/spool'
import { StatusBadge } from './StatusBadge'

interface InventoryGridProps {
  spools: readonly Spool[]
}

export function InventoryGrid({ spools }: InventoryGridProps) {
  return (
    <ul
      aria-label="Spools in grid view"
      className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3"
      role="list"
    >
      {spools.map((spool) => {
        const remainingPercent = Math.min(
          100,
          Math.max(0, spool.remaining_percent),
        )

        return (
          <li key={spool.id}>
            <article className="flex h-full min-h-64 flex-col rounded-lg border border-line bg-surface p-5 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h3 className="font-mono text-sm font-bold tracking-[0.08em] text-ink">
                    {spool.code}
                  </h3>
                  <p className="mt-2 truncate text-sm text-ink-muted">
                    <span>{spool.manufacturer.name}</span>{' '}
                    <span className="font-semibold text-ink">{spool.material.name}</span>
                  </p>
                </div>
                <StatusBadge status={spool.status} />
              </div>

              <div className="mt-5 flex items-center gap-2 text-sm text-ink">
                <span
                  aria-label={`Color: ${spool.color_name}`}
                  className={`size-3.5 shrink-0 rounded-full border border-black/15 shadow-sm dark:border-white/20 ${
                    spool.color_hex ? '' : 'bg-line'
                  }`}
                  style={
                    spool.color_hex
                      ? { backgroundColor: spool.color_hex }
                      : undefined
                  }
                />
                <span>{spool.color_name}</span>
              </div>

              <div className="mt-6">
                <div className="flex items-end justify-between gap-4">
                  <p className="text-xl font-semibold tracking-tight text-ink">
                    {formatWeight(Number(spool.current_filament_weight_g))}
                  </p>
                  <p className="font-mono text-sm font-semibold text-ink">
                    {formatPercent(spool.remaining_percent)}
                  </p>
                </div>
                <div
                  aria-label={`${spool.code} remaining filament`}
                  aria-valuemax={100}
                  aria-valuemin={0}
                  aria-valuenow={remainingPercent}
                  className="mt-3 h-1.5 overflow-hidden rounded-full bg-line"
                  role="progressbar"
                >
                  <div
                    className="h-full rounded-full bg-accent"
                    style={{ width: `${remainingPercent}%` }}
                  />
                </div>
              </div>

              <p className="mt-auto flex items-center gap-2 border-t border-line pt-5 text-xs text-ink-muted">
                <MapPin aria-hidden="true" className="size-3.5 shrink-0" />
                <span className="truncate">{spool.location?.name ?? 'Unassigned'}</span>
              </p>
            </article>
          </li>
        )
      })}
    </ul>
  )
}
