import type { Spool } from '../../types/spool'
import { SpoolCard } from '../spool/SpoolCard'

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
      {spools.map((spool) => (
        <li key={spool.id}>
          <a
            aria-label={`View spool ${spool.code}`}
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
