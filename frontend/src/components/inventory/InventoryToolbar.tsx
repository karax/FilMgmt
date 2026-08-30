import { Grid2X2, Plus, SlidersHorizontal, TableProperties } from 'lucide-react'

export type InventoryView = 'grid' | 'table'

interface InventoryToolbarProps {
  count: number | null | undefined
  view: InventoryView
  onViewChange: (view: InventoryView) => void
  activeFilterCount: number
  filtersOpen: boolean
  onFiltersToggle: () => void
}

export function InventoryToolbar({
  count,
  view,
  onViewChange,
  activeFilterCount,
  filtersOpen,
  onFiltersToggle,
}: InventoryToolbarProps) {
  const countLabel =
    count === null
      ? 'Loading spools…'
      : count === undefined
        ? 'Spool count unavailable'
      : `${count} ${count === 1 ? 'spool' : 'spools'}`

  return (
    <div className="mb-6 border-b border-line pb-5 sm:flex sm:items-end sm:justify-between sm:gap-6">
      <div>
        <div className="mb-3 flex items-center gap-3">
          <span aria-hidden="true" className="h-px w-8 bg-accent" />
          <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">
            Module / 02
          </p>
        </div>
        <h2
          className="text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl"
          id="inventory-title"
        >
          Inventory
        </h2>
        <p className="mt-2 text-sm leading-6 text-ink-muted sm:text-base">
          Manage and track your filament spools.
        </p>
        <p className="mt-2 font-mono text-xs font-semibold text-ink" aria-live="polite">
          {countLabel}
        </p>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 sm:mt-0">
        <button aria-expanded={filtersOpen} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-line bg-surface px-3.5 text-sm font-bold text-ink transition-colors hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onClick={onFiltersToggle} type="button"><SlidersHorizontal aria-hidden="true" className="size-4" />Filters{activeFilterCount ? ` (${activeFilterCount})` : ''}</button>
        <a className="inline-flex min-h-10 items-center gap-2 rounded-md bg-accent px-3.5 text-sm font-bold text-sidebar transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" href="/inventory/new"><Plus aria-hidden="true" className="size-4" />Add Spool</a>
        <div
          aria-label="Inventory view"
          className="inline-flex rounded-md border border-line bg-surface p-1 shadow-sm"
          role="group"
        >
          <ViewButton
            active={view === 'grid'}
            icon={Grid2X2}
            label="Grid view"
            onClick={() => onViewChange('grid')}
          />
          <ViewButton
            active={view === 'table'}
            icon={TableProperties}
            label="Table view"
            onClick={() => onViewChange('table')}
          />
        </div>
      </div>
    </div>
  )
}

interface ViewButtonProps {
  active: boolean
  icon: typeof Grid2X2
  label: string
  onClick: () => void
}

function ViewButton({ active, icon: Icon, label, onClick }: ViewButtonProps) {
  return (
    <button
      aria-label={label}
      aria-pressed={active}
      className={`inline-flex min-h-9 items-center gap-2 rounded px-3 text-xs font-bold uppercase tracking-[0.1em] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
        active
          ? 'bg-accent-soft text-accent'
          : 'text-ink-muted hover:bg-surface-raised hover:text-ink'
      }`}
      onClick={onClick}
      type="button"
    >
      <Icon aria-hidden="true" className="size-4" strokeWidth={1.8} />
      <span>{label.replace(' view', '')}</span>
    </button>
  )
}
