import { Boxes } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { formatWeight, type MaterialGroup } from '../../lib/inventory'

interface MaterialSummaryProps {
  groups: readonly MaterialGroup[]
}

export function MaterialSummary({ groups }: MaterialSummaryProps) {
  const { t } = useTranslation()
  return (
    <section
      aria-labelledby="materials-title"
      className="rounded-lg border border-line bg-surface shadow-sm"
    >
      <div className="flex items-center gap-3 border-b border-line px-5 py-4 sm:px-6">
        <span className="grid size-9 place-items-center rounded-md bg-accent-soft text-accent">
          <Boxes aria-hidden="true" className="size-[1.1rem]" strokeWidth={1.8} />
        </span>
        <div>
          <h2 className="text-base font-semibold tracking-tight" id="materials-title">
            {t('dashboard.materials')}
          </h2>
          <p className="text-xs text-ink-muted">{t('dashboard.active')} · {t('inventory.material').toLowerCase()}</p>
        </div>
      </div>

      {groups.length === 0 ? (
        <p className="px-5 py-8 text-sm text-ink-muted sm:px-6">
          {t('dashboard.noSpoolsDescription')}
        </p>
      ) : (
        <ul className="divide-y divide-line" role="list">
          {groups.map(({ material, spoolCount, totalWeightG }) => (
            <li
              className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-5 py-4 sm:px-6"
              key={material.id}
            >
              <div className="min-w-0">
                <p className="truncate font-semibold text-ink">{material.name}</p>
                <p className="mt-0.5 font-mono text-[0.65rem] uppercase tracking-[0.14em] text-ink-muted">
                  {material.category}
                </p>
              </div>
              <div className="text-right">
                <p className="font-semibold text-ink">{formatWeight(totalWeightG)}</p>
                <p className="mt-0.5 text-xs text-ink-muted">
                  {t('inventory.spool', { count: spoolCount })}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
