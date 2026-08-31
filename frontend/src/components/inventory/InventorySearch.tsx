import { Search, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function InventorySearch({ value, onChange, onClear }: { value: string; onChange: (value: string) => void; onClear: () => void }) {
  const { t } = useTranslation()
  return <div className="mb-4 relative max-w-xl"><label className="sr-only" htmlFor="inventory-search">{t('inventory.search')}</label><Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-muted" /><input className="min-h-11 w-full rounded-md border border-line bg-surface py-2 pl-10 pr-10 text-sm text-ink placeholder:text-ink-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" id="inventory-search" onChange={(event) => onChange(event.target.value)} placeholder={t('inventory.searchPlaceholder')} type="search" value={value} />{value && <button aria-label={t('inventory.clearSearch')} className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded text-ink-muted hover:bg-surface-raised hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onClick={onClear} type="button"><X aria-hidden="true" className="size-4" /></button>}</div>
}
