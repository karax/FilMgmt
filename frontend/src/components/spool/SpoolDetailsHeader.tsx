import { ArrowLeft, Droplets } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { Spool } from '../../types/spool'
import { SpoolColorIndicator } from './SpoolColorIndicator'
import { SpoolStatusBadge } from './SpoolStatusBadge'

export function SpoolDetailsHeader({ spool }: { spool: Spool }) {
  return (
    <header>
      <Link
        className="inline-flex items-center gap-2 rounded text-sm font-semibold text-ink-muted transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
        to="/inventory"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Back to Inventory
      </Link>
      <div className="mt-6 flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.15em] text-accent">Spool details</p>
          <h1 id="spool-details-title" className="mt-2 font-mono text-3xl font-bold tracking-tight text-ink sm:text-4xl">{spool.code}</h1>
          <p className="mt-2 text-lg font-semibold text-ink">
            {spool.manufacturer.name} <span className="text-ink-muted">{spool.material.name}</span>
          </p>
          {spool.product_name && <p className="mt-1 text-sm text-ink-muted">{spool.product_name}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <SpoolStatusBadge status={spool.status} />
          <span className="inline-flex items-center gap-2 text-sm text-ink">
            <SpoolColorIndicator colorHex={spool.color_hex} colorName={spool.color_name} />
            {spool.color_name}
          </span>
        </div>
      </div>
      {spool.needs_drying && (
        <p className="mt-5 inline-flex items-center gap-2 rounded-md border border-sky-500/35 bg-sky-500/10 px-3 py-2 text-sm font-semibold text-sky-700 dark:text-sky-300">
          <Droplets aria-hidden="true" className="size-4" /> Needs drying
        </p>
      )}
      {spool.status === 'ARCHIVED' && (
        <p className="mt-5 rounded-md border border-amber-500/35 bg-amber-500/10 px-3 py-2 text-sm text-ink">
          This archived spool is retained as a historical record.
        </p>
      )}
    </header>
  )
}
