import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { SpoolColorIndicator } from '../spool/SpoolColorIndicator'
import { SpoolStatusBadge } from '../spool/SpoolStatusBadge'
import { formatPercent, formatWeight } from '../../lib/inventory'
import type { Spool } from '../../types/spool'

interface InventoryTableProps {
  spools: readonly Spool[]
}

export function InventoryTable({ spools }: InventoryTableProps) {
  const { t } = useTranslation()
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface shadow-sm">
      <table className="w-full border-collapse text-left" aria-label={t('inventory.tableAria')}>
        <thead className="bg-surface-raised">
          <tr className="border-b border-line">
            <ColumnHeader>{t('inventory.spoolColumn')}</ColumnHeader>
            <ColumnHeader className="hidden lg:table-cell">{t('inventory.manufacturer')}</ColumnHeader>
            <ColumnHeader>{t('inventory.material')}</ColumnHeader>
            <ColumnHeader className="hidden md:table-cell">{t('inventory.color')}</ColumnHeader>
            <ColumnHeader>{t('inventory.remaining')}</ColumnHeader>
            <ColumnHeader className="hidden sm:table-cell">{t('inventory.weight')}</ColumnHeader>
            <ColumnHeader>{t('inventory.status')}</ColumnHeader>
            <ColumnHeader className="hidden xl:table-cell">{t('inventory.location')}</ColumnHeader>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {spools.map((spool) => (
            <tr className="transition-colors hover:bg-surface-raised/75" key={spool.id}>
              <th
                className="whitespace-nowrap px-3 py-4 font-mono text-xs font-bold tracking-wide text-ink sm:px-4"
                scope="row"
              >
                <a
                  className="rounded text-accent underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                  href={`/spools/${encodeURIComponent(spool.code)}`}
                >
                  {spool.display_name && <span className="mb-1 block max-w-48 truncate font-sans text-sm font-semibold tracking-normal text-ink">{spool.display_name}</span>}
                  <span>{spool.code}</span>
                </a>
              </th>
              <Cell className="hidden lg:table-cell">{spool.manufacturer.name}</Cell>
              <Cell className="font-semibold text-ink">{spool.material.name}</Cell>
              <Cell className="hidden md:table-cell">
                <span className="inline-flex items-center gap-2">
                  <SpoolColorIndicator
                    colorHex={spool.color_hex}
                    colorName={spool.color_name}
                  />
                  {spool.color_name}
                </span>
              </Cell>
              <Cell className="whitespace-nowrap font-mono font-semibold text-ink">
                {formatPercent(spool.remaining_percent)}
              </Cell>
              <Cell className="hidden whitespace-nowrap font-mono sm:table-cell">
                {formatWeight(Number(spool.current_filament_weight_g))}
              </Cell>
              <Cell>
                <SpoolStatusBadge status={spool.status} />
              </Cell>
              <Cell className="hidden xl:table-cell">
                {spool.location?.name ?? '—'}
              </Cell>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface ColumnHeaderProps {
  children: string
  className?: string
}

function ColumnHeader({ children, className = '' }: ColumnHeaderProps) {
  return (
    <th
      className={`whitespace-nowrap px-3 py-3 font-mono text-[0.62rem] font-bold uppercase tracking-[0.12em] text-ink-muted sm:px-4 ${className}`}
      scope="col"
    >
      {children}
    </th>
  )
}

interface CellProps {
  children: ReactNode
  className?: string
}

function Cell({ children, className = '' }: CellProps) {
  return (
    <td className={`px-3 py-4 text-sm text-ink-muted sm:px-4 ${className}`}>
      {children}
    </td>
  )
}
