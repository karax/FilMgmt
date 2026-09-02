import { AlertCircle, RefreshCw } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'

import { SpoolForm } from '../components/spool/SpoolForm'
import { useManufacturers } from '../hooks/useManufacturers'
import { useMaterials } from '../hooks/useMaterials'
import { useSpool } from '../hooks/useSpool'
import { useUpdateSpool } from '../hooks/useSpoolMutations'
import type { CreateSpoolPayload, Spool, UpdateSpoolPayload } from '../types/spool'

function numeric(value: number | string | null): string {
  return value == null ? '' : String(value)
}

function localDateTime(value: string | null): string {
  return value ? value.slice(0, 16) : ''
}

function formValues(spool: Spool) {
  return {
    manufacturerId: String(spool.manufacturer_id), materialId: String(spool.material_id),
    displayName: spool.display_name ?? '', productName: spool.product_name ?? '', colorName: spool.color_name, colorHex: spool.color_hex ?? '',
    diameter: numeric(spool.diameter_mm), initialWeight: numeric(spool.initial_filament_weight_g),
    currentWeight: numeric(spool.current_filament_weight_g), emptySpoolWeight: numeric(spool.empty_spool_weight_g),
    purchasePrice: numeric(spool.purchase_price), storeName: spool.store_name ?? '', currency: spool.currency, purchaseDate: spool.purchase_date ?? '',
    status: spool.status === 'OPEN' ? ('OPEN' as const) : ('SEALED' as const), needsDrying: spool.needs_drying,
    lastDriedAt: localDateTime(spool.last_dried_at), nozzleTempMin: numeric(spool.nozzle_temp_min),
    nozzleTempMax: numeric(spool.nozzle_temp_max), bedTempMin: numeric(spool.bed_temp_min),
    bedTempMax: numeric(spool.bed_temp_max), notes: spool.notes ?? '',
  }
}

function editablePayload(payload: CreateSpoolPayload): UpdateSpoolPayload {
  const { current_filament_weight_g: _weight, status: _status, ...editable } = payload
  return editable
}

export function EditSpoolPage() {
  const { code } = useParams()
  const navigate = useNavigate()
  const spoolQuery = useSpool(code)
  const manufacturers = useManufacturers()
  const materials = useMaterials()
  const update = useUpdateSpool()

  const catalogLoading = manufacturers.isPending || materials.isPending
  const loadError = spoolQuery.error || manufacturers.error || materials.error

  if (spoolQuery.isPending || catalogLoading) return <EditSkeleton />
  if (!code || !spoolQuery.data || loadError) {
    return <section className="rounded-lg border border-red-500/30 bg-surface px-5 py-12 text-center" role="alert"><AlertCircle aria-hidden="true" className="mx-auto size-6 text-red-600 dark:text-red-400" /><h1 className="mt-4 text-xl font-semibold text-ink">Unable to load spool for editing.</h1><button className="mt-6 inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar" onClick={() => { void spoolQuery.refetch(); void manufacturers.refetch(); void materials.refetch() }} type="button"><RefreshCw className="size-4" />Retry</button></section>
  }

  const spool = spoolQuery.data
  return (
    <section aria-labelledby="edit-spool-title" className="mx-auto max-w-4xl">
      <div className="mb-7 border-b border-line pb-5"><p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">Inventory / {spool.code} / Edit</p><h1 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl" id="edit-spool-title">Edit Spool</h1><p className="mt-2 text-sm text-ink-muted">Update descriptive, purchase, and print-setting details for {spool.code}.</p></div>
      <SpoolForm
        initialValues={formValues(spool)} isSubmitting={update.isPending}
        manufacturers={manufacturers.data ?? []} materials={materials.data ?? []} mode="edit"
        onCancel={() => navigate(`/spools/${encodeURIComponent(spool.code)}`)}
        onSubmit={(payload) => update.mutate({ code: spool.code, payload: editablePayload(payload) }, { onSuccess: () => navigate(`/spools/${encodeURIComponent(spool.code)}`, { replace: true, state: { feedback: 'Spool updated successfully.' } }) })}
        submitError={update.error}
      />
    </section>
  )
}

function EditSkeleton() { return <div aria-label="Loading spool editor" className="space-y-6" role="status"><div className="h-10 w-52 animate-pulse rounded bg-surface-raised" />{Array.from({ length: 4 }, (_, index) => <div className="h-44 animate-pulse rounded-lg bg-surface-raised" key={index} />)}</div> }
