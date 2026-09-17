import type { Spool } from '../../types/spool'
import { SpoolCard } from '../spool/SpoolCard'
import { useTranslation } from 'react-i18next'

interface InventoryGridProps {
  spools: readonly Spool[]
}

export function InventoryGrid({ spools }: InventoryGridProps) {
  const { t } = useTranslation()
  return (
    <ul
      aria-label={t('inventory.gridAria')}
      className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3"
      role="list"
    >
      {spools.map((spool) => (
        <li key={spool.id}>
          <a
            aria-label={t('spool.view', { code: spool.code })}
            className="block h-full rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            href={`/spools/${encodeURIComponent(spool.code)}`}
          >
            <SpoolCard spool={spool} />
          </a>
        </li>
      ))}
    </ul>
  )
}
