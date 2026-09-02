import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useManufacturers } from '../../hooks/useManufacturers'
import { useMaterials } from '../../hooks/useMaterials'
import { spoolStatuses } from '../../lib/spoolFilters'
import type { SpoolFilters, SpoolStatus } from '../../types/spool'

interface InventoryFiltersProps { filters: SpoolFilters; onApply: (filters: SpoolFilters) => void; onClear: () => void }

export function InventoryFilters({ filters, onApply, onClear }: InventoryFiltersProps) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState(filters)
  const [validationError, setValidationError] = useState<string | null>(null)
  const { data: manufacturers = [] } = useManufacturers()
  const { data: materials = [] } = useMaterials()
  useEffect(() => { setDraft(filters); setValidationError(null) }, [filters])

  const set = <K extends keyof SpoolFilters>(key: K, value: SpoolFilters[K]) => setDraft((current) => ({ ...current, [key]: value }))
  const number = (key: keyof SpoolFilters, raw: string) => set(key, raw === '' ? undefined : Number(raw) as never)
  const apply = () => {
    const values = [draft.minWeightG, draft.maxWeightG, draft.minRemainingPercent, draft.maxRemainingPercent]
    if (values.some((value) => value != null && (!Number.isFinite(value) || value < 0)) || [draft.minRemainingPercent, draft.maxRemainingPercent].some((value) => value != null && value > 100)) { setValidationError(t('filters.invalidRange')); return }
    if ((draft.minWeightG != null && draft.maxWeightG != null && draft.minWeightG > draft.maxWeightG) || (draft.minRemainingPercent != null && draft.maxRemainingPercent != null && draft.minRemainingPercent > draft.maxRemainingPercent)) { setValidationError(t('filters.invalidMinMax')); return }
    setValidationError(null); onApply(draft)
  }
  const clear = () => { setDraft({}); setValidationError(null); onClear() }

  return <form className="mb-6 rounded-lg border border-line bg-surface p-4 shadow-sm sm:p-5" onSubmit={(event) => { event.preventDefault(); apply() }}>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <FilterSelect id="manufacturer" label={t('inventory.manufacturer')} onChange={(value) => set('manufacturerId', value ? Number(value) : undefined)} value={draft.manufacturerId ?? ''}><option value="">{t('filters.allManufacturers')}</option>{manufacturers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</FilterSelect>
      <FilterSelect id="material" label={t('inventory.material')} onChange={(value) => set('materialId', value ? Number(value) : undefined)} value={draft.materialId ?? ''}><option value="">{t('filters.allMaterials')}</option>{materials.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</FilterSelect>
      <FilterSelect id="status" label={t('inventory.status')} onChange={(value) => set('status', value ? value as SpoolStatus : undefined)} value={draft.status ?? ''}><option value="">{t('filters.allStatuses')}</option>{spoolStatuses.map((status) => <option key={status} value={status}>{t(`status.${status}`)}</option>)}</FilterSelect>
      <FilterSelect id="needs-drying" label={t('filters.needsDrying')} onChange={(value) => set('needsDrying', value === '' ? undefined : value === 'true')} value={draft.needsDrying === undefined ? '' : String(draft.needsDrying)}><option value="">{t('filters.any')}</option><option value="true">{t('filters.needsDrying')}</option><option value="false">{t('filters.doesNotNeedDrying')}</option></FilterSelect>
      <NumberInput id="min-weight" label={t('filters.minWeight')} max={undefined} onChange={(value) => number('minWeightG', value)} suffix="g" value={draft.minWeightG} />
      <NumberInput id="max-weight" label={t('filters.maxWeight')} max={undefined} onChange={(value) => number('maxWeightG', value)} suffix="g" value={draft.maxWeightG} />
      <label className="flex items-end gap-2 pb-2 text-sm font-medium text-ink"><input checked={draft.includeArchived === true} className="size-4 accent-accent" onChange={(event) => set('includeArchived', event.target.checked ? true : undefined)} type="checkbox" />{t('filters.includeArchived')}</label>
      <NumberInput id="min-remaining" label={t('filters.minRemaining')} max={100} onChange={(value) => number('minRemainingPercent', value)} suffix="%" value={draft.minRemainingPercent} />
      <NumberInput id="max-remaining" label={t('filters.maxRemaining')} max={100} onChange={(value) => number('maxRemainingPercent', value)} suffix="%" value={draft.maxRemainingPercent} />
    </div>
    {validationError && <p className="mt-4 text-sm font-medium text-red-600 dark:text-red-400" role="alert">{validationError}</p>}
    <div className="mt-5 flex flex-wrap justify-end gap-3"><button className="rounded-md px-4 py-2 text-sm font-semibold text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onClick={clear} type="button">{t('inventory.clearFilters')}</button><button className="rounded-md bg-accent px-4 py-2 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" type="submit">{t('inventory.applyFilters')}</button></div>
  </form>
}

function FilterSelect({ id, label, value, onChange, children }: { id: string; label: string; value: string | number; onChange: (value: string) => void; children: React.ReactNode }) { return <label className="grid gap-1.5 text-sm font-medium text-ink" htmlFor={id}>{label}<select className="min-h-10 rounded-md border border-line bg-surface-raised px-3 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" id={id} onChange={(event) => onChange(event.target.value)} value={value}>{children}</select></label> }
function NumberInput({ id, label, value, max, suffix, onChange }: { id: string; label: string; value: number | undefined; max: number | undefined; suffix: string; onChange: (value: string) => void }) { return <label className="grid gap-1.5 text-sm font-medium text-ink" htmlFor={id}>{label}<span className="flex"><input className="min-h-10 min-w-0 flex-1 rounded-l-md border border-line bg-surface-raised px-3 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" id={id} max={max} min="0" onChange={(event) => onChange(event.target.value)} type="number" value={value ?? ''} /><span className="grid min-h-10 place-items-center rounded-r-md border border-l-0 border-line px-3 text-ink-muted">{suffix}</span></span></label> }
