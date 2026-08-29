import {
  AlertCircle,
  Archive,
  Droplets,
  Gauge,
  PackageOpen,
} from 'lucide-react'

import { CriticalSpools } from '../components/dashboard/CriticalSpools'
import { DashboardSkeleton } from '../components/dashboard/DashboardSkeleton'
import { MaterialSummary } from '../components/dashboard/MaterialSummary'
import { StatCard } from '../components/dashboard/StatCard'
import { useSpools } from '../hooks/useSpools'
import {
  calculateInventorySummary,
  formatWeight,
  groupSpoolsByMaterial,
  sortCriticalSpools,
} from '../lib/inventory'

export function DashboardPage() {
  const { data: spools, error, isFetching, isPending, refetch } = useSpools()

  if (isPending) {
    return (
      <section aria-labelledby="dashboard-overview-title">
        <DashboardHeading />
        <DashboardSkeleton />
      </section>
    )
  }

  if (error) {
    return (
      <section aria-labelledby="dashboard-overview-title">
        <DashboardHeading />
        <div
          className="rounded-lg border border-red-500/30 bg-surface px-5 py-10 text-center shadow-sm sm:px-8"
          role="alert"
        >
          <span className="mx-auto grid size-11 place-items-center rounded-full bg-red-500/10 text-red-600 dark:text-red-400">
            <AlertCircle aria-hidden="true" className="size-5" />
          </span>
          <h2 className="mt-4 text-lg font-semibold text-ink">
            Unable to load inventory.
          </h2>
          <p className="mt-2 text-sm text-ink-muted">
            Please check the backend connection.
          </p>
          <button
            className="mt-6 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-wait disabled:opacity-60"
            disabled={isFetching}
            onClick={() => void refetch()}
            type="button"
          >
            {isFetching ? 'Retrying…' : 'Retry'}
          </button>
        </div>
      </section>
    )
  }

  const inventory = spools ?? []
  const summary = calculateInventorySummary(inventory)
  const materialGroups = groupSpoolsByMaterial(inventory)
  const criticalSpools = sortCriticalSpools(inventory).slice(0, 6)

  return (
    <section aria-labelledby="dashboard-overview-title">
      <DashboardHeading />

      <section aria-label="Inventory summary">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:gap-4 xl:grid-cols-5">
          <StatCard
            icon={Archive}
            subtitle="active inventory"
            title="Total Spools"
            value={String(summary.totalSpools)}
          />
          <StatCard
            icon={Gauge}
            subtitle="available filament"
            title="Available Filament"
            value={formatWeight(summary.totalWeightG)}
          />
          <StatCard
            icon={AlertCircle}
            subtitle="require attention"
            title="Low Spools"
            tone="warning"
            value={String(summary.lowCount)}
          />
          <StatCard
            icon={PackageOpen}
            subtitle="no filament left"
            title="Empty Spools"
            tone="danger"
            value={String(summary.emptyCount)}
          />
          <StatCard
            icon={Droplets}
            subtitle="flagged by inventory"
            title="Needs Drying"
            value={String(summary.needsDryingCount)}
          />
        </div>
      </section>

      {inventory.length === 0 && (
        <div className="mt-6 rounded-lg border border-dashed border-line bg-surface/65 px-5 py-8 text-center sm:px-8">
          <p className="font-semibold text-ink">No filament spools yet.</p>
          <p className="mt-1 text-sm text-ink-muted">
            Inventory totals and alerts will update when your first spool is added.
          </p>
        </div>
      )}

      <div className="mt-6 grid items-start gap-6 xl:grid-cols-[minmax(18rem,0.75fr)_minmax(0,1.25fr)]">
        <MaterialSummary groups={materialGroups} />
        <CriticalSpools spools={criticalSpools} />
      </div>
    </section>
  )
}

function DashboardHeading() {
  return (
    <div className="mb-6 sm:flex sm:items-end sm:justify-between sm:gap-6">
      <div>
        <div className="mb-3 flex items-center gap-3">
          <span aria-hidden="true" className="h-px w-8 bg-accent" />
          <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">
            Module / 01
          </p>
        </div>
        <h2
          className="text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl"
          id="dashboard-overview-title"
        >
          Inventory overview
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted sm:text-base">
          Live operational status across your active filament stock.
        </p>
      </div>
      <p className="mt-3 font-mono text-[0.65rem] uppercase tracking-[0.16em] text-ink-muted sm:mt-0">
        Source / Spool registry
      </p>
    </div>
  )
}
