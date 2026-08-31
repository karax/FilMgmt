import { AlertCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { ActiveFilters } from '../components/inventory/ActiveFilters'
import { InventoryEmptyState } from '../components/inventory/InventoryEmptyState'
import { InventoryGrid } from '../components/inventory/InventoryGrid'
import { InventoryFilters } from '../components/inventory/InventoryFilters'
import { InventorySearch } from '../components/inventory/InventorySearch'
import { InventorySkeleton } from '../components/inventory/InventorySkeleton'
import { InventoryTable } from '../components/inventory/InventoryTable'
import {
  InventoryToolbar,
  type InventoryView,
} from '../components/inventory/InventoryToolbar'
import { useSpools } from '../hooks/useSpools'
import { useLocations } from '../hooks/useLocations'
import { useManufacturers } from '../hooks/useManufacturers'
import { useMaterials } from '../hooks/useMaterials'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { activeFilterCount, filtersFromSearchParams, filtersToSearchParams } from '../lib/spoolFilters'
import type { SpoolFilters } from '../types/spool'

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
  const { t } = useTranslation()
  const [view, setView] = useState<InventoryView>(getInitialView)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = filtersFromSearchParams(searchParams)
  const [searchInput, setSearchInput] = useState(filters.search ?? '')
  const debouncedSearch = useDebouncedValue(searchInput)
  const { data: manufacturers = [] } = useManufacturers(filtersOpen || filters.manufacturerId !== undefined)
  const { data: materials = [] } = useMaterials(filtersOpen || filters.materialId !== undefined)
  const { data: locations = [] } = useLocations(filtersOpen || filters.locationId !== undefined)
  const { data: spools, error, isFetching, isPending, refetch } = useSpools(filters)
  const hasFilters = activeFilterCount(filters) > 0
  const structuredFilterCount = activeFilterCount({ ...filters, search: undefined })

  const applyFilters = (nextFilters: SpoolFilters) => setSearchParams(filtersToSearchParams(nextFilters))
  useEffect(() => {
    const search = debouncedSearch.trim() || undefined
    if (search !== filters.search) applyFilters({ ...filters, search })
  }, [debouncedSearch, filters])
  useEffect(() => { setSearchInput(filters.search ?? '') }, [filters.search])
  const removeFilter = (key: keyof SpoolFilters) => {
    const nextFilters = { ...filters }
    delete nextFilters[key]
    applyFilters(nextFilters)
  }
  const filterLabels: Partial<Record<keyof SpoolFilters, string>> = {
    search: filters.search ? `${t('inventory.search')}: “${filters.search}”` : undefined,
    manufacturerId: manufacturers.find((item) => item.id === filters.manufacturerId)?.name ?? (filters.manufacturerId == null ? undefined : `${t('inventory.manufacturer')} ${filters.manufacturerId}`),
    materialId: materials.find((item) => item.id === filters.materialId)?.name ?? (filters.materialId == null ? undefined : `${t('inventory.material')} ${filters.materialId}`),
    locationId: locations.find((item) => item.id === filters.locationId)?.name ?? (filters.locationId == null ? undefined : `${t('inventory.location')} ${filters.locationId}`),
    status: filters.status ? t(`status.${filters.status}`) : undefined, needsDrying: filters.needsDrying === true ? t('filters.needsDrying') : t('filters.doesNotNeedDrying'),
    minWeightG: filters.minWeightG == null ? undefined : `${t('filters.minWeight')} ${filters.minWeightG} g`, maxWeightG: filters.maxWeightG == null ? undefined : `${t('filters.maxWeight')} ${filters.maxWeightG} g`,
    minRemainingPercent: filters.minRemainingPercent == null ? undefined : `${t('filters.minRemaining')} ${filters.minRemainingPercent}%`, maxRemainingPercent: filters.maxRemainingPercent == null ? undefined : `${t('filters.maxRemaining')} ${filters.maxRemainingPercent}%`, includeArchived: t('filters.includeArchived'),
  }

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
        activeFilterCount={structuredFilterCount}
        filtersOpen={filtersOpen}
        onFiltersToggle={() => setFiltersOpen((open) => !open)}
      />

      <InventorySearch onChange={setSearchInput} onClear={() => { setSearchInput(''); applyFilters({ ...filters, search: undefined }) }} value={searchInput} />

      {filtersOpen && <InventoryFilters filters={filters} onApply={applyFilters} onClear={() => applyFilters({ search: filters.search })} />}
      <ActiveFilters filters={filters} labels={filterLabels} onRemove={removeFilter} />

      {typeof window.history.state?.usr?.createdSpoolCode === 'string' && (
        <p className="mb-5 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 text-sm font-medium text-ink" role="status">
          {t('inventory.created', { code: window.history.state.usr.createdSpoolCode })}
        </p>
      )}

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
            {t('inventory.unable')}
          </h3>
          <p className="mt-2 text-sm text-ink-muted">
            {t('inventory.connection')}
          </p>
          <button
            className="mt-6 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60"
            disabled={isFetching}
            onClick={() => void refetch()}
            type="button"
          >
            {isFetching ? t('inventory.retrying') : t('common.retry')}
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
        hasFilters ? <div className="rounded-lg border border-dashed border-line bg-surface px-5 py-14 text-center shadow-sm"><h3 className="text-lg font-semibold text-ink">{filters.search && structuredFilterCount === 0 ? t('inventory.noSearch', { search: filters.search }) : filters.search ? t('inventory.noSearchAndFilters') : t('inventory.noMatch')}</h3><p className="mt-2 text-sm text-ink-muted">{t('inventory.tryAnother')}</p><div className="mt-5 flex justify-center gap-3">{filters.search && <button className="rounded-md border border-line px-4 py-2.5 text-sm font-bold text-ink" onClick={() => { setSearchInput(''); applyFilters({ ...filters, search: undefined }) }} type="button">{t('inventory.clearSearch')}</button>}<button className="rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar" onClick={() => applyFilters({ search: filters.search })} type="button">{t('inventory.clearFilters')}</button></div></div> : <InventoryEmptyState />
      )}
    </section>
  )
}
