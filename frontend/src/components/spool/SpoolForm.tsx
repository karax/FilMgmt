import { AlertCircle, LoaderCircle } from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { isApiError } from '../../api/client'
import { mapSpoolApiValidationErrors, type SpoolFormField } from '../../lib/spoolValidation'
import type {
  CreateSpoolPayload,
  Location,
  Manufacturer,
  Material,
} from '../../types/spool'

type FormValues = {
  manufacturerId: string
  materialId: string
  locationId: string
  displayName: string
  productName: string
  colorName: string
  colorHex: string
  diameter: string
  initialWeight: string
  currentWeight: string
  emptySpoolWeight: string
  purchasePrice: string
  currency: string
  purchaseDate: string
  status: 'SEALED' | 'OPEN'
  needsDrying: boolean
  lastDriedAt: string
  nozzleTempMin: string
  nozzleTempMax: string
  bedTempMin: string
  bedTempMax: string
  notes: string
}

type FieldErrors = Partial<Record<keyof FormValues, string>>
type PrintSettingKey = 'nozzleTempMin' | 'nozzleTempMax' | 'bedTempMin' | 'bedTempMax'

export interface SpoolFormProps {
  manufacturers: Manufacturer[]
  materials: Material[]
  locations: Location[]
  isSubmitting: boolean
  submitError: unknown
  onCancel: () => void
  onSubmit: (payload: CreateSpoolPayload) => void
  mode?: 'create' | 'edit'
  initialValues?: Partial<FormValues>
}

const initialValues: FormValues = {
  manufacturerId: '',
  materialId: '',
  locationId: '',
  displayName: '',
  productName: '',
  colorName: '',
  colorHex: '',
  diameter: '1.75',
  initialWeight: '1000',
  currentWeight: '1000',
  emptySpoolWeight: '',
  purchasePrice: '',
  currency: 'EUR',
  purchaseDate: '',
  status: 'SEALED',
  needsDrying: false,
  lastDriedAt: '',
  nozzleTempMin: '',
  nozzleTempMax: '',
  bedTempMin: '',
  bedTempMax: '',
  notes: '',
}

const inputClass =
  'mt-1.5 w-full rounded-md border border-line bg-surface px-3 py-2.5 text-sm text-ink shadow-sm outline-none transition-colors placeholder:text-ink-muted focus:border-accent focus:ring-2 focus:ring-accent/20 disabled:cursor-not-allowed disabled:opacity-60'
const labelClass = 'block text-sm font-semibold text-ink'
const helpClass = 'mt-1.5 text-xs leading-5 text-ink-muted'
const printSettingKeys: readonly PrintSettingKey[] = [
  'nozzleTempMin',
  'nozzleTempMax',
  'bedTempMin',
  'bedTempMax',
]

function optionalText(value: string): string | null {
  return value.trim() || null
}

function optionalNumber(value: string): number | null {
  return value.trim() === '' ? null : Number(value)
}

function errorMessage(error: unknown, hasFieldErrors: boolean, t: (key: string) => string): string | null {
  if (!isApiError(error)) return null
  if (error.status === 422) return hasFieldErrors ? t('errors.reviewFields') : t('errors.validationFallback')
  if (error.status === 404) return t('errors.selectedMissing')
  if (error.status === 409) return t('errors.conflict')
  return t('errors.save')
}

function validate(values: FormValues): FieldErrors {
  const errors: FieldErrors = {}
  const initialWeight = Number(values.initialWeight)
  const currentWeight = Number(values.currentWeight)
  const diameter = Number(values.diameter)
  const purchasePrice = optionalNumber(values.purchasePrice)
  const nozzleMin = optionalNumber(values.nozzleTempMin)
  const nozzleMax = optionalNumber(values.nozzleTempMax)
  const bedMin = optionalNumber(values.bedTempMin)
  const bedMax = optionalNumber(values.bedTempMax)

  if (!values.manufacturerId) errors.manufacturerId = 'Select a manufacturer.'
  if (!values.materialId) errors.materialId = 'Select a material.'
  if (!values.colorName.trim()) errors.colorName = 'Color name is required.'
  if (!Number.isFinite(diameter) || diameter <= 0) errors.diameter = 'Diameter must be greater than zero.'
  if (!Number.isFinite(initialWeight) || initialWeight <= 0) {
    errors.initialWeight = 'Initial weight must be greater than zero.'
  }
  if (!Number.isFinite(currentWeight) || currentWeight < 0) {
    errors.currentWeight = 'Current weight cannot be negative.'
  } else if (Number.isFinite(initialWeight) && currentWeight > initialWeight) {
    errors.currentWeight = 'Current weight cannot exceed initial weight.'
  }
  if (purchasePrice !== null && (!Number.isFinite(purchasePrice) || purchasePrice < 0)) {
    errors.purchasePrice = 'Purchase price cannot be negative.'
  }
  if (nozzleMin !== null && (!Number.isFinite(nozzleMin) || nozzleMin < 0 || nozzleMin > 500)) {
    errors.nozzleTempMin = 'Use a valid temperature.'
  }
  if (nozzleMax !== null && (!Number.isFinite(nozzleMax) || nozzleMax < 0 || nozzleMax > 500)) {
    errors.nozzleTempMax = 'Use a valid temperature.'
  }
  if (bedMin !== null && (!Number.isFinite(bedMin) || bedMin < 0 || bedMin > 500)) {
    errors.bedTempMin = 'Use a valid temperature.'
  }
  if (bedMax !== null && (!Number.isFinite(bedMax) || bedMax < 0 || bedMax > 500)) {
    errors.bedTempMax = 'Use a valid temperature.'
  }
  if (nozzleMin !== null && nozzleMax !== null && nozzleMin > nozzleMax) {
    errors.nozzleTempMax = 'Maximum must be at least the minimum.'
  }
  if (bedMin !== null && bedMax !== null && bedMin > bedMax) {
    errors.bedTempMax = 'Maximum must be at least the minimum.'
  }
  if (values.colorHex && !/^#[0-9A-Fa-f]{6}$/.test(values.colorHex)) {
    errors.colorHex = 'Use a hex color such as #000000.'
  }

  return errors
}

function InputError({ error }: { error?: string }) {
  return error ? <p className="mt-1.5 text-xs font-medium text-red-600 dark:text-red-400">{error}</p> : null
}

function FormField({
  children,
  error,
  label,
  hint,
}: {
  children: React.ReactNode
  error?: string
  label: string
  hint?: string
}) {
  return (
    <label className={labelClass}>
      {label}
      {children}
      {hint && <span className={helpClass}>{hint}</span>}
      <InputError error={error} />
    </label>
  )
}

export function SpoolForm({
  manufacturers,
  materials,
  locations,
  isSubmitting,
  submitError,
  onCancel,
  onSubmit,
  mode = 'create',
  initialValues: providedInitialValues,
}: SpoolFormProps) {
  const { t } = useTranslation()
  const [values, setValues] = useState<FormValues>(() => ({ ...initialValues, ...providedInitialValues }))
  const [errors, setErrors] = useState<FieldErrors>({})
  const [apiFormError, setApiFormError] = useState<string | null>(null)
  const [printSettingsEdited, setPrintSettingsEdited] = useState(mode === 'edit')
  const [materialDefaultsMessage, setMaterialDefaultsMessage] = useState<string | null>(null)

  const focusFirstError = (fieldErrors: Partial<Record<SpoolFormField, string>>) => {
    const first = Object.keys(fieldErrors)[0]
    if (!first) return
    window.setTimeout(() => document.getElementById(`spool-${first}`)?.focus(), 0)
  }

  useEffect(() => {
    const mapped = mapSpoolApiValidationErrors(submitError, (issue) => (
      issue.type === 'extra_forbidden'
        ? t('errors.extraForbidden')
        : typeof issue.msg === 'string' ? issue.msg : t('errors.validationFallback')
    ))
    if (!mapped) return
    setErrors((current) => ({ ...current, ...mapped.fieldErrors }))
    setApiFormError(mapped.formError)
    focusFirstError(mapped.fieldErrors)
  }, [submitError])

  const update = <Key extends keyof FormValues>(key: Key, value: FormValues[Key]) => {
    setValues((current) => ({ ...current, [key]: value }))
    setErrors((current) => ({ ...current, [key]: undefined }))
    setApiFormError(null)
  }

  const selectedMaterial = materials.find((material) => material.id === Number(values.materialId))

  const materialDefaultValues = (material: Material): Pick<FormValues, PrintSettingKey> => ({
    nozzleTempMin: material.default_nozzle_temp_min === null ? '' : String(material.default_nozzle_temp_min),
    nozzleTempMax: material.default_nozzle_temp_max === null ? '' : String(material.default_nozzle_temp_max),
    bedTempMin: material.default_bed_temp_min === null ? '' : String(material.default_bed_temp_min),
    bedTempMax: material.default_bed_temp_max === null ? '' : String(material.default_bed_temp_max),
  })

  const applyMaterialDefaults = (material: Material) => {
    setValues((current) => ({ ...current, ...materialDefaultValues(material) }))
    setErrors((current) => {
      const next = { ...current }
      for (const key of printSettingKeys) next[key] = undefined
      return next
    })
    setPrintSettingsEdited(false)
    setMaterialDefaultsMessage(t('spool.defaultsFrom', { material: material.name }))
  }

  const selectMaterial = (materialId: string) => {
    const nextMaterial = materials.find((material) => material.id === Number(materialId))
    const materialChanged = values.materialId !== '' && values.materialId !== materialId
    update('materialId', materialId)

    if (!nextMaterial) {
      setMaterialDefaultsMessage(null)
      return
    }
    if (!materialChanged || !printSettingsEdited) {
      applyMaterialDefaults(nextMaterial)
      return
    }
    setMaterialDefaultsMessage(t('spool.materialChanged'))
  }

  const updatePrintSetting = (key: PrintSettingKey, value: string) => {
    update(key, value)
    setPrintSettingsEdited(true)
    setMaterialDefaultsMessage(null)
  }

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const nextErrors = validate(values)
    setErrors(nextErrors)
    setApiFormError(null)
    if (Object.keys(nextErrors).length > 0 || manufacturers.length === 0 || materials.length === 0) {
      focusFirstError(nextErrors)
      return
    }

    onSubmit({
      manufacturer_id: Number(values.manufacturerId),
      material_id: Number(values.materialId),
      location_id: values.locationId ? Number(values.locationId) : null,
      display_name: optionalText(values.displayName),
      product_name: optionalText(values.productName),
      color_name: values.colorName.trim(),
      color_hex: optionalText(values.colorHex)?.toUpperCase() ?? null,
      diameter_mm: Number(values.diameter),
      initial_filament_weight_g: Number(values.initialWeight),
      current_filament_weight_g: optionalNumber(values.currentWeight),
      empty_spool_weight_g: optionalNumber(values.emptySpoolWeight),
      purchase_price: optionalNumber(values.purchasePrice),
      currency: values.currency.trim().toUpperCase(),
      purchase_date: optionalText(values.purchaseDate),
      nozzle_temp_min: optionalNumber(values.nozzleTempMin),
      nozzle_temp_max: optionalNumber(values.nozzleTempMax),
      bed_temp_min: optionalNumber(values.bedTempMin),
      bed_temp_max: optionalNumber(values.bedTempMax),
      status: values.status,
      needs_drying: values.needsDrying,
      last_dried_at: values.lastDriedAt ? new Date(values.lastDriedAt).toISOString() : null,
      notes: optionalText(values.notes),
    })
  }

  const disabled = isSubmitting || manufacturers.length === 0 || materials.length === 0
  const apiError = apiFormError ?? errorMessage(submitError, Object.keys(errors).some((key) => errors[key as keyof FormValues]), t)

  return (
    <form className="space-y-8" noValidate onSubmit={submit}>
      {apiError && (
        <div className="flex gap-3 rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-ink" role="alert">
          <AlertCircle aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-red-600 dark:text-red-400" />
          <p>{apiError}</p>
        </div>
      )}

      <FormSection title={t('spool.basic')}>
        <FormField error={errors.displayName} label={t('spool.name')} hint={t('spool.nameHint')}>
          <input aria-invalid={Boolean(errors.displayName)} className={`${inputClass} ${errors.displayName ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-displayName" onChange={(event) => update('displayName', event.target.value)} placeholder={t('spool.namePlaceholder')} value={values.displayName} />
        </FormField>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField error={errors.manufacturerId} label={t('spool.manufacturer')}>
            <select aria-invalid={Boolean(errors.manufacturerId)} className={`${inputClass} ${errors.manufacturerId ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-manufacturerId" onChange={(event) => update('manufacturerId', event.target.value)} value={values.manufacturerId}>
              <option value="">{t('filters.allManufacturers')}</option>
              {manufacturers.map((manufacturer) => <option key={manufacturer.id} value={manufacturer.id}>{manufacturer.name}</option>)}
            </select>
          </FormField>
          <FormField error={errors.materialId} label={t('spool.material')}>
            <select aria-invalid={Boolean(errors.materialId)} className={`${inputClass} ${errors.materialId ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-materialId" onChange={(event) => selectMaterial(event.target.value)} value={values.materialId}>
              <option value="">{t('filters.allMaterials')}</option>
              {materials.map((material) => <option key={material.id} value={material.id}>{material.name}</option>)}
            </select>
          </FormField>
        </div>
        {manufacturers.length === 0 && <p className="mt-4 text-sm text-red-600 dark:text-red-400">No manufacturers available. Create a manufacturer first.</p>}
        {materials.length === 0 && <p className="mt-4 text-sm text-red-600 dark:text-red-400">No materials available. Create a material first.</p>}
      </FormSection>

      <FormSection title={t('spool.materialColor')}>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField error={errors.productName} label={t('spool.productName')} hint={t('spool.productHint')}>
            <input aria-invalid={Boolean(errors.productName)} className={`${inputClass} ${errors.productName ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-productName" onChange={(event) => update('productName', event.target.value)} placeholder="PLA+ HS" value={values.productName} />
          </FormField>
          <FormField error={errors.colorName} label={t('spool.colorName')}>
            <input aria-invalid={Boolean(errors.colorName)} className={`${inputClass} ${errors.colorName ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-colorName" onChange={(event) => update('colorName', event.target.value)} placeholder="Black" value={values.colorName} />
          </FormField>
          <FormField error={errors.colorHex} label={t('spool.colorHex')} hint={`${t('common.optional')} — #RRGGBB`}>
            <div className="mt-1.5 flex gap-2">
              <input aria-label="Choose color" className="h-11 w-12 cursor-pointer rounded-md border border-line bg-surface p-1" disabled={isSubmitting} onChange={(event) => update('colorHex', event.target.value.toUpperCase())} type="color" value={/^#[0-9A-Fa-f]{6}$/.test(values.colorHex) ? values.colorHex : '#000000'} />
              <input aria-label="Color Hex" aria-invalid={Boolean(errors.colorHex)} className={`${inputClass} mt-0 ${errors.colorHex ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-colorHex" onChange={(event) => update('colorHex', event.target.value)} placeholder="#000000" value={values.colorHex} />
            </div>
          </FormField>
          <FormField error={errors.diameter} label={t('spool.diameter')}>
            <div className="relative mt-1.5"><input aria-invalid={Boolean(errors.diameter)} className={`${inputClass} mt-0 pr-12 ${errors.diameter ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-diameter" min="0.5" onChange={(event) => update('diameter', event.target.value)} step="0.01" type="number" value={values.diameter} /><span className="pointer-events-none absolute right-3 top-2.5 text-sm text-ink-muted">mm</span></div>
          </FormField>
        </div>
      </FormSection>

      <FormSection title={t('inventory.weight')}>
        <div className="grid gap-5 sm:grid-cols-2">
          <NumberField error={errors.initialWeight} id="initialWeight" label={t('spool.initialWeight')} onChange={(value) => update('initialWeight', value)} value={values.initialWeight} />
          {mode === 'create' && <NumberField error={errors.currentWeight} id="currentWeight" label={t('spool.currentWeight')} onChange={(value) => update('currentWeight', value)} value={values.currentWeight} />}
          <NumberField error={errors.emptySpoolWeight} id="emptySpoolWeight" label={t('spool.emptyWeight')} onChange={(value) => update('emptySpoolWeight', value)} optional value={values.emptySpoolWeight} />
        </div>
      </FormSection>

      <FormSection title={t('spool.purchase')}>
        <div className="grid gap-5 sm:grid-cols-3">
          <NumberField error={errors.purchasePrice} id="purchasePrice" label={t('spool.price')} onChange={(value) => update('purchasePrice', value)} optional unit="" value={values.purchasePrice} />
          <FormField error={errors.currency} label={t('spool.currency')}>
            <select aria-invalid={Boolean(errors.currency)} className={`${inputClass} ${errors.currency ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-currency" onChange={(event) => update('currency', event.target.value)} value={values.currency}><option>EUR</option><option>USD</option><option>GBP</option></select>
          </FormField>
          <FormField error={errors.purchaseDate} label="Purchase Date" hint="Optional"><input aria-invalid={Boolean(errors.purchaseDate)} className={`${inputClass} ${errors.purchaseDate ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-purchaseDate" onChange={(event) => update('purchaseDate', event.target.value)} type="date" value={values.purchaseDate} /></FormField>
        </div>
      </FormSection>

      <FormSection title={t('spool.printSettings')} optional>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-line bg-surface-raised px-3 py-2.5">
          <p aria-live="polite" className="text-xs text-ink-muted">
            {materialDefaultsMessage ?? t('spool.selectMaterialDefaults')}
          </p>
          <button
            className="rounded border border-line bg-surface px-2.5 py-1.5 text-xs font-semibold text-ink transition-colors hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isSubmitting || !selectedMaterial}
            onClick={() => selectedMaterial && applyMaterialDefaults(selectedMaterial)}
            type="button"
          >
            {t('spool.applyDefaults')}
          </button>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <NumberField error={errors.nozzleTempMin} id="nozzleTempMin" label={t('spool.nozzleMin')} onChange={(value) => updatePrintSetting('nozzleTempMin', value)} optional unit="°C" value={values.nozzleTempMin} />
          <NumberField error={errors.nozzleTempMax} id="nozzleTempMax" label={t('spool.nozzleMax')} onChange={(value) => updatePrintSetting('nozzleTempMax', value)} optional unit="°C" value={values.nozzleTempMax} />
          <NumberField error={errors.bedTempMin} id="bedTempMin" label={t('spool.bedMin')} onChange={(value) => updatePrintSetting('bedTempMin', value)} optional unit="°C" value={values.bedTempMin} />
          <NumberField error={errors.bedTempMax} id="bedTempMax" label={t('spool.bedMax')} onChange={(value) => updatePrintSetting('bedTempMax', value)} optional unit="°C" value={values.bedTempMax} />
        </div>
      </FormSection>

      <FormSection title={mode === 'create' ? 'Storage & Status' : 'Storage'}>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField error={errors.locationId} label="Location" hint="Optional">
            <select aria-invalid={Boolean(errors.locationId)} className={`${inputClass} ${errors.locationId ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-locationId" onChange={(event) => update('locationId', event.target.value)} value={values.locationId}><option value="">No location</option>{locations.map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}</select>
          </FormField>
          {mode === 'create' && <FormField label="Initial Status"><select className={inputClass} disabled={isSubmitting} onChange={(event) => update('status', event.target.value as FormValues['status'])} value={values.status}><option value="SEALED">SEALED</option><option value="OPEN">OPEN</option></select></FormField>}
        </div>
        <label className={`mt-5 flex cursor-pointer items-center gap-3 rounded-md border bg-surface-raised px-3 py-3 text-sm text-ink ${errors.needsDrying ? 'border-red-500' : 'border-line'}`}><input aria-invalid={Boolean(errors.needsDrying)} checked={values.needsDrying} className="size-4 accent-accent" disabled={isSubmitting} id="spool-needsDrying" onChange={(event) => update('needsDrying', event.target.checked)} type="checkbox" />Needs drying<InputError error={errors.needsDrying} /></label>
        {mode === 'edit' && <FormField error={errors.lastDriedAt} label="Last Dried At" hint="Optional"><input aria-invalid={Boolean(errors.lastDriedAt)} className={`${inputClass} ${errors.lastDriedAt ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-lastDriedAt" onChange={(event) => update('lastDriedAt', event.target.value)} type="datetime-local" value={values.lastDriedAt} /></FormField>}
      </FormSection>

      <FormSection title="Notes" optional>
        <textarea aria-invalid={Boolean(errors.notes)} className={`${inputClass} min-h-28 resize-y ${errors.notes ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-notes" onChange={(event) => update('notes', event.target.value)} placeholder="Optional notes about this spool" value={values.notes} />
        <InputError error={errors.notes} />
      </FormSection>

      <div className="flex flex-col-reverse gap-3 border-t border-line pt-6 sm:flex-row sm:justify-end">
        <button className="rounded-md border border-line px-4 py-2.5 text-sm font-bold text-ink transition-colors hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" disabled={isSubmitting} onClick={onCancel} type="button">{t('common.cancel')}</button>
        <button className="inline-flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar transition-opacity focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60" disabled={disabled} type="submit">{isSubmitting && <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />}{isSubmitting ? (mode === 'edit' ? t('spool.saving') : t('spool.creating')) : (mode === 'edit' ? t('spool.save') : t('spool.create'))}</button>
      </div>
    </form>
  )
}

function FormSection({ children, title, optional = false }: { children: React.ReactNode; title: string; optional?: boolean }) {
  return <section aria-labelledby={`${title.toLowerCase().replaceAll(' ', '-')}-title`}><div className="mb-4 flex items-baseline gap-2"><h2 className="text-base font-semibold text-ink" id={`${title.toLowerCase().replaceAll(' ', '-')}-title`}>{title}</h2>{optional && <span className="font-mono text-[0.65rem] uppercase tracking-[0.15em] text-ink-muted">Optional</span>}</div>{children}</section>
}

function NumberField({ error, hint, id, label, onChange, optional = false, unit = 'g', value }: { error?: string; hint?: string; id: string; label: string; onChange: (value: string) => void; optional?: boolean; unit?: string; value: string }) {
  return <FormField error={error} hint={hint ?? (optional ? 'Optional' : undefined)} label={label}><div className="relative mt-1.5"><input aria-invalid={Boolean(error)} className={`${inputClass} mt-0 ${unit ? 'pr-12' : ''} ${error ? 'border-red-500 focus:border-red-500' : ''}`} id={`spool-${id}`} min="0" onChange={(event) => onChange(event.target.value)} step="any" type="number" value={value} />{unit && <span className="pointer-events-none absolute right-3 top-2.5 text-sm text-ink-muted">{unit}</span>}</div></FormField>
}
