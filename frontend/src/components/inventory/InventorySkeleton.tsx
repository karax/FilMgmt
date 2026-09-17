import type { InventoryView } from './InventoryToolbar'
import { useTranslation } from 'react-i18next'

interface InventorySkeletonProps {
  view: InventoryView
}

export function InventorySkeleton({ view }: InventorySkeletonProps) {
  const { t } = useTranslation()
  if (view === 'table') {
    return (
      <div
        aria-busy="true"
        aria-label={t('inventory.loading')}
        className="overflow-hidden rounded-lg border border-line bg-surface"
        role="status"
      >
        <span className="sr-only">{t('inventory.loading')}</span>
        <div aria-hidden="true" className="h-11 animate-pulse border-b border-line bg-surface-raised" />
        {Array.from({ length: 6 }, (_, index) => (
          <div
            aria-hidden="true"
            className="flex h-16 animate-pulse items-center gap-6 border-b border-line px-4 last:border-b-0"
            key={index}
          >
            <span className="h-3 w-20 rounded bg-line" />
            <span className="h-3 w-24 rounded bg-line" />
            <span className="ml-auto h-6 w-16 rounded bg-line" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div
      aria-busy="true"
      aria-label={t('inventory.loading')}
      className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3"
      role="status"
    >
      <span className="sr-only">{t('inventory.loading')}</span>
      {Array.from({ length: 6 }, (_, index) => (
        <div
          aria-hidden="true"
          className="h-64 animate-pulse rounded-lg border border-line bg-surface"
          key={index}
        />
      ))}
    </div>
  )
}
