import { AlertCircle } from 'lucide-react'
import { useState } from 'react'

import { InventoryEmptyState } from '../components/inventory/InventoryEmptyState'
import { InventoryGrid } from '../components/inventory/InventoryGrid'
import { InventorySkeleton } from '../components/inventory/InventorySkeleton'
import { InventoryTable } from '../components/inventory/InventoryTable'
import {
  InventoryToolbar,
  type InventoryView,
} from '../components/inventory/InventoryToolbar'
import { useSpools } from '../hooks/useSpools'

export const INVENTORY_VIEW_STORAGE_KEY = 'fcc-inventory-view'

function getInitialView(): InventoryView {
  try {
    return window.localStorage.getItem(INVENTORY_VIEW_STORAGE_KEY) === 'table'
      ? 'table'
      : 'grid'
  } catch {
    return 'grid'
  }
}

export function InventoryPage() {
  const [view, setView] = useState<InventoryView>(getInitialView)
  const { data: spools, error, isFetching, isPending, refetch } = useSpools()

  const changeView = (nextView: InventoryView) => {
    setView(nextView)
    try {
      window.localStorage.setItem(INVENTORY_VIEW_STORAGE_KEY, nextView)
    } catch {
      // The view still changes while storage is unavailable.
    }
  }

  return (
    <section aria-labelledby="inventory-title">
      <InventoryToolbar
        count={isPending ? null : error ? undefined : (spools?.length ?? 0)}
        onViewChange={changeView}
        view={view}
      />

      {isPending && <InventorySkeleton view={view} />}

      {error && !isPending && (
        <div
          className="rounded-lg border border-red-500/30 bg-surface px-5 py-10 text-center shadow-sm sm:px-8"
          role="alert"
        >
          <AlertCircle
            aria-hidden="true"
            className="mx-auto size-6 text-red-600 dark:text-red-400"
          />
          <h3 className="mt-4 text-lg font-semibold text-ink">
            Unable to load inventory.
          </h3>
          <p className="mt-2 text-sm text-ink-muted">
            Please check the backend connection.
          </p>
          <button
            className="mt-6 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60"
            disabled={isFetching}
            onClick={() => void refetch()}
            type="button"
          >
            {isFetching ? 'Retrying…' : 'Retry'}
          </button>
        </div>
      )}

      {!isPending && !error && spools && spools.length > 0 && view === 'grid' && (
        <InventoryGrid spools={spools} />
      )}

      {!isPending && !error && spools && spools.length > 0 && view === 'table' && (
        <InventoryTable spools={spools} />
      )}

      {!isPending && !error && spools?.length === 0 && (
        <InventoryEmptyState />
      )}
    </section>
  )
}
