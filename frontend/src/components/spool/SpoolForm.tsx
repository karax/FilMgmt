import { AlertCircle, LoaderCircle } from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { isApiError } from '../../api/client'
import {
  mapSpoolApiValidationErrors,
  MAX_SPOOL_FILAMENT_WEIGHT_G,
  MAX_SPOOL_PURCHASE_PRICE,
  type SpoolFormField,
} from '../../lib/spoolValidation'
import type {
  CreateSpoolPayload,
  Manufacturer,
  Material,
} from '../../types/spool'

type FormValues = {
  manufacturerId: string
  materialId: string
  displayName: string
  productName: string
  colorName: string
  colorHex: string
  diameter: string
  initialWeight: string
  currentWeight: string
  emptySpoolWeight: string
  purchasePrice: string
  storeName: string
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
  displayName: '',
  productName: '',
  colorName: '',
  colorHex: '',
  diameter: '1.75',
  initialWeight: '1000',
  currentWeight: '1000',
  emptySpoolWeight: '',
  purchasePrice: '',
  storeName: '',
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

function normalizeNamePart(value: string): string {
  return value.trim().replaceAll(/\s+/g, ' ')
}

function errorMessage(error: unknown, hasFieldErrors: boolean, t: (key: string) => string): string | null {
  if (!isApiError(error)) return null
  if (error.status === 422) return hasFieldErrors ? t('errors.reviewFields') : t('errors.validationFallback')
  if (error.status === 404) return t('errors.selectedMissing')
  if (error.status === 409) return t('errors.conflict')
  return t('errors.save')
}

function formatMaximumPrice(currency: string, language: string): string {
  try {
    return new Intl.NumberFormat(language, {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(MAX_SPOOL_PURCHASE_PRICE).replaceAll(/\s/g, '')
  } catch {
    return String(MAX_SPOOL_PURCHASE_PRICE)
  }
}

function validate(
  values: FormValues,
  t: (key: string, options?: Record<string, unknown>) => string,
  language: string,
): FieldErrors {
  const errors: FieldErrors = {}
  const initialWeight = Number(values.initialWeight)
  const currentWeight = Number(values.currentWeight)
  const diameter = Number(values.diameter)
  const purchasePrice = optionalNumber(values.purchasePrice)
  const nozzleMin = optionalNumber(values.nozzleTempMin)
  const nozzleMax = optionalNumber(values.nozzleTempMax)
  const bedMin = optionalNumber(values.bedTempMin)
  const bedMax = optionalNumber(values.bedTempMax)

  if (!values.manufacturerId) errors.manufacturerId = t('spool.validation.selectManufacturer')
  if (!values.materialId) errors.materialId = t('spool.validation.selectMaterial')
  if (!values.colorName.trim()) errors.colorName = t('spool.validation.colorRequired')
  if (!Number.isFinite(diameter) || diameter <= 0) errors.diameter = t('spool.validation.positiveDiameter')
  if (!Number.isFinite(initialWeight) || initialWeight <= 0) {
    errors.initialWeight = t('spool.validation.positiveInitialWeight')
  } else if (initialWeight > MAX_SPOOL_FILAMENT_WEIGHT_G) {
    errors.initialWeight = t('spool.validation.maxFilamentWeight')
  }
  if (!Number.isFinite(currentWeight) || currentWeight < 0) {
    errors.currentWeight = t('spool.validation.currentWeightNegative')
  } else if (currentWeight > MAX_SPOOL_FILAMENT_WEIGHT_G) {
    errors.currentWeight = t('spool.validation.maxFilamentWeight')
  } else if (Number.isFinite(initialWeight) && currentWeight > initialWeight) {
    errors.currentWeight = t('spool.validation.currentExceedsInitial')
  }
  if (purchasePrice !== null && (!Number.isFinite(purchasePrice) || purchasePrice < 0)) {
    errors.purchasePrice = t('spool.validation.purchasePriceNegative')
  } else if (purchasePrice !== null && purchasePrice > MAX_SPOOL_PURCHASE_PRICE) {
    errors.purchasePrice = t('spool.validation.maxPurchasePrice', {
      price: formatMaximumPrice(values.currency, language),
    })
  }
  if (nozzleMin !== null && (!Number.isFinite(nozzleMin) || nozzleMin < 0 || nozzleMin > 500)) {
    errors.nozzleTempMin = t('spool.validation.validTemperature')
  }
  if (nozzleMax !== null && (!Number.isFinite(nozzleMax) || nozzleMax < 0 || nozzleMax > 500)) {
    errors.nozzleTempMax = t('spool.validation.validTemperature')
  }
  if (bedMin !== null && (!Number.isFinite(bedMin) || bedMin < 0 || bedMin > 500)) {
    errors.bedTempMin = t('spool.validation.validTemperature')
  }
  if (bedMax !== null && (!Number.isFinite(bedMax) || bedMax < 0 || bedMax > 500)) {
    errors.bedTempMax = t('spool.validation.validTemperature')
  }
  if (nozzleMin !== null && nozzleMax !== null && nozzleMin > nozzleMax) {
    errors.nozzleTempMax = t('spool.validation.maximumAtLeastMinimum')
  }
  if (bedMin !== null && bedMax !== null && bedMin > bedMax) {
    errors.bedTempMax = t('spool.validation.maximumAtLeastMinimum')
  }
  if (values.colorHex && !/^#[0-9A-Fa-f]{6}$/.test(values.colorHex)) {
    errors.colorHex = t('spool.validation.validHexColor')
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
  isSubmitting,
  submitError,
  onCancel,
  onSubmit,
  mode = 'create',
  initialValues: providedInitialValues,
}: SpoolFormProps) {
  const { i18n, t } = useTranslation()
  const [values, setValues] = useState<FormValues>(() => ({ ...initialValues, ...providedInitialValues }))
  const [errors, setErrors] = useState<FieldErrors>({})
  const [apiFormError, setApiFormError] = useState<string | null>(null)
  const [displayNameEdited, setDisplayNameEdited] = useState(mode === 'edit')
  const [printSettingsEdited, setPrintSettingsEdited] = useState(mode === 'edit')
  const [materialDefaultsMessage, setMaterialDefaultsMessage] = useState<string | null>(null)

  const focusFirstError = (fieldErrors: Partial<Record<SpoolFormField, string>>) => {
    const first = Object.keys(fieldErrors)[0]
    if (!first) return
    window.setTimeout(() => document.getElementById(`spool-${first}`)?.focus(), 0)
  }

  useEffect(() => {
    const mapped = mapSpoolApiValidationErrors(submitError, (issue) => {
      if (issue.type === 'extra_forbidden') return t('errors.extraForbidden')
      if (typeof issue.msg !== 'string') return t('errors.validationFallback')
      if (issue.msg.includes('Filament weight cannot exceed 2000 g.')) {
        return t('spool.validation.maxFilamentWeight')
      }
      if (issue.msg.includes('Purchase price cannot exceed 100.')) {
        return t('spool.validation.maxPurchasePrice', {
          price: formatMaximumPrice(
            values.currency,
            i18n.resolvedLanguage ?? i18n.language,
          ),
        })
      }
      return t('spool.validation.invalidValue')
    })
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

  useEffect(() => {
    if (mode !== 'create' || displayNameEdited) return

    const manufacturerName = normalizeNamePart(
      manufacturers.find(
        (manufacturer) => manufacturer.id === Number(values.manufacturerId),
      )?.name ?? '',
    )
    const colorName = normalizeNamePart(values.colorName)
    const generatedName = manufacturerName && colorName
      ? `${manufacturerName} ${colorName}`
      : ''

    setValues((current) => current.displayName === generatedName
      ? current
      : { ...current, displayName: generatedName })
  }, [displayNameEdited, manufacturers, mode, values.colorName, values.manufacturerId])

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
    const nextErrors = validate(
      values,
      t,
      i18n.resolvedLanguage ?? i18n.language,
    )
    setErrors(nextErrors)
    setApiFormError(null)
    if (Object.keys(nextErrors).length > 0 || manufacturers.length === 0 || materials.length === 0) {
      focusFirstError(nextErrors)
      return
    }

    onSubmit({
      manufacturer_id: Number(values.manufacturerId),
      material_id: Number(values.materialId),
      display_name: optionalText(values.displayName),
      product_name: optionalText(values.productName),
      color_name: values.colorName.trim(),
      color_hex: optionalText(values.colorHex)?.toUpperCase() ?? null,
      diameter_mm: Number(values.diameter),
      initial_filament_weight_g: Number(values.initialWeight),
      current_filament_weight_g: optionalNumber(values.currentWeight),
      empty_spool_weight_g: optionalNumber(values.emptySpoolWeight),
      purchase_price: optionalNumber(values.purchasePrice),
      store_name: optionalText(values.storeName),
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
          <input aria-invalid={Boolean(errors.displayName)} className={`${inputClass} ${errors.displayName ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-displayName" onChange={(event) => { setDisplayNameEdited(true); update('displayName', event.target.value) }} placeholder={t('spool.namePlaceholder')} value={values.displayName} />
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
        {(manufacturers.length === 0 || materials.length === 0) && (
          <div className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-ink">
            {manufacturers.length === 0 && <p>{t('spool.manufacturerEmpty')}</p>}
            {materials.length === 0 && <p className={manufacturers.length === 0 ? 'mt-2' : ''}>{t('spool.materialEmpty')}</p>}
            <Link className="mt-3 inline-flex font-semibold text-accent underline underline-offset-4" to="/settings/catalogs">{t('spool.openCatalogs')}</Link>
          </div>
        )}
      </FormSection>

      <FormSection title={t('spool.materialColor')}>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField error={errors.productName} label={t('spool.productName')} hint={t('spool.productHint')}>
            <input aria-invalid={Boolean(errors.productName)} className={`${inputClass} ${errors.productName ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-productName" onChange={(event) => update('productName', event.target.value)} placeholder="PLA+ HS" value={values.productName} />
          </FormField>
          <FormField error={errors.colorName} label={t('spool.colorName')}>
            <input aria-invalid={Boolean(errors.colorName)} className={`${inputClass} ${errors.colorName ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-colorName" onChange={(event) => update('colorName', event.target.value)} placeholder={t('spool.colorNamePlaceholder')} value={values.colorName} />
          </FormField>
          <FormField error={errors.colorHex} label={t('spool.colorHex')} hint={`${t('common.optional')} — #RRGGBB`}>
            <div className="mt-1.5 flex gap-2">
              <input aria-label={t('spool.chooseColor')} className="h-11 w-12 cursor-pointer rounded-md border border-line bg-surface p-1" disabled={isSubmitting} onChange={(event) => update('colorHex', event.target.value.toUpperCase())} type="color" value={/^#[0-9A-Fa-f]{6}$/.test(values.colorHex) ? values.colorHex : '#000000'} />
              <input aria-label={t('spool.colorHex')} aria-invalid={Boolean(errors.colorHex)} className={`${inputClass} mt-0 ${errors.colorHex ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-colorHex" onChange={(event) => update('colorHex', event.target.value)} placeholder="#000000" value={values.colorHex} />
            </div>
          </FormField>
          <FormField error={errors.diameter} label={t('spool.diameter')}>
            <div className="relative mt-1.5"><input aria-invalid={Boolean(errors.diameter)} className={`${inputClass} mt-0 pr-12 ${errors.diameter ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-diameter" min="0.5" onChange={(event) => update('diameter', event.target.value)} step="0.01" type="number" value={values.diameter} /><span className="pointer-events-none absolute right-3 top-2.5 text-sm text-ink-muted">mm</span></div>
          </FormField>
        </div>
      </FormSection>

      <FormSection title={t('inventory.weight')}>
        <div className="grid gap-5 sm:grid-cols-2">
          <NumberField error={errors.initialWeight} id="initialWeight" label={t('spool.initialWeight')} max={MAX_SPOOL_FILAMENT_WEIGHT_G} onChange={(value) => update('initialWeight', value)} value={values.initialWeight} />
          {mode === 'create' && <NumberField error={errors.currentWeight} id="currentWeight" label={t('spool.currentWeight')} max={MAX_SPOOL_FILAMENT_WEIGHT_G} onChange={(value) => update('currentWeight', value)} value={values.currentWeight} />}
          <NumberField error={errors.emptySpoolWeight} id="emptySpoolWeight" label={t('spool.emptyWeight')} onChange={(value) => update('emptySpoolWeight', value)} optional value={values.emptySpoolWeight} />
        </div>
      </FormSection>

      <FormSection title={t('spool.purchase')}>
        <div className="grid gap-5 sm:grid-cols-3">
          <FormField error={errors.storeName} label={t('spool.storeName')} hint={t('common.optional')}>
            <input aria-invalid={Boolean(errors.storeName)} className={`${inputClass} ${errors.storeName ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-storeName" onChange={(event) => update('storeName', event.target.value)} value={values.storeName} />
          </FormField>
          <NumberField error={errors.purchasePrice} id="purchasePrice" label={t('spool.price')} max={MAX_SPOOL_PURCHASE_PRICE} onChange={(value) => update('purchasePrice', value)} optional unit="" value={values.purchasePrice} />
          <FormField error={errors.currency} label={t('spool.currency')}>
            <select aria-invalid={Boolean(errors.currency)} className={`${inputClass} ${errors.currency ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-currency" onChange={(event) => update('currency', event.target.value)} value={values.currency}><option>EUR</option><option>USD</option><option>GBP</option></select>
          </FormField>
          <FormField error={errors.purchaseDate} label={t('spool.purchaseDate')} hint={t('common.optional')}><input aria-invalid={Boolean(errors.purchaseDate)} className={`${inputClass} ${errors.purchaseDate ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-purchaseDate" onChange={(event) => update('purchaseDate', event.target.value)} type="date" value={values.purchaseDate} /></FormField>
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

      <FormSection title={t('spool.status')}>
        {mode === 'create' && <div className="grid gap-5 sm:grid-cols-2"><FormField label={t('spool.initialStatus')}><select className={inputClass} disabled={isSubmitting} onChange={(event) => update('status', event.target.value as FormValues['status'])} value={values.status}><option value="SEALED">{t('status.SEALED')}</option><option value="OPEN">{t('status.OPEN')}</option></select></FormField></div>}
        <label className={`mt-5 flex cursor-pointer items-center gap-3 rounded-md border bg-surface-raised px-3 py-3 text-sm text-ink ${errors.needsDrying ? 'border-red-500' : 'border-line'}`}><input aria-invalid={Boolean(errors.needsDrying)} checked={values.needsDrying} className="size-4 accent-accent" disabled={isSubmitting} id="spool-needsDrying" onChange={(event) => update('needsDrying', event.target.checked)} type="checkbox" />{t('spool.needsDrying')}<InputError error={errors.needsDrying} /></label>
        {mode === 'edit' && <FormField error={errors.lastDriedAt} label={t('spool.lastDried')} hint={t('common.optional')}><input aria-invalid={Boolean(errors.lastDriedAt)} className={`${inputClass} ${errors.lastDriedAt ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-lastDriedAt" onChange={(event) => update('lastDriedAt', event.target.value)} type="datetime-local" value={values.lastDriedAt} /></FormField>}
      </FormSection>

      <FormSection title={t('spool.notes')} optional>
        <textarea aria-invalid={Boolean(errors.notes)} className={`${inputClass} min-h-28 resize-y ${errors.notes ? 'border-red-500 focus:border-red-500' : ''}`} disabled={isSubmitting} id="spool-notes" onChange={(event) => update('notes', event.target.value)} placeholder={t('spool.notesPlaceholder')} value={values.notes} />
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
  const { t } = useTranslation()
  return <section aria-labelledby={`${title.toLowerCase().replaceAll(' ', '-')}-title`}><div className="mb-4 flex items-baseline gap-2"><h2 className="text-base font-semibold text-ink" id={`${title.toLowerCase().replaceAll(' ', '-')}-title`}>{title}</h2>{optional && <span className="font-mono text-[0.65rem] uppercase tracking-[0.15em] text-ink-muted">{t('common.optional')}</span>}</div>{children}</section>
}

function NumberField({ error, hint, id, label, max, onChange, optional = false, unit = 'g', value }: { error?: string; hint?: string; id: string; label: string; max?: number; onChange: (value: string) => void; optional?: boolean; unit?: string; value: string }) {
  const { t } = useTranslation()
  return <FormField error={error} hint={hint ?? (optional ? t('common.optional') : undefined)} label={label}><div className="relative mt-1.5"><input aria-invalid={Boolean(error)} className={`${inputClass} mt-0 ${unit ? 'pr-12' : ''} ${error ? 'border-red-500 focus:border-red-500' : ''}`} id={`spool-${id}`} max={max} min="0" onChange={(event) => onChange(event.target.value)} step="any" type="number" value={value} />{unit && <span className="pointer-events-none absolute right-3 top-2.5 text-sm text-ink-muted">{unit}</span>}</div></FormField>
}
