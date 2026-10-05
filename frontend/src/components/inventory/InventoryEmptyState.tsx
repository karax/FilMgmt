import { PackageOpen } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function InventoryEmptyState() {
  const { t } = useTranslation()
  return (
    <div className="rounded-lg border border-dashed border-line bg-surface px-5 py-14 text-center shadow-sm sm:px-8">
      <span className="mx-auto grid size-12 place-items-center rounded-full bg-accent-soft text-accent">
        <PackageOpen aria-hidden="true" className="size-5" strokeWidth={1.8} />
      </span>
      <h3 className="mt-5 text-lg font-semibold text-ink">
        {t('inventory.empty')}
      </h3>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-ink-muted">
        {t('inventory.emptyDescription')}
      </p>
    </div>
  )
}
