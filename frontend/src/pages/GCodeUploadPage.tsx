import { AlertCircle, CheckCircle2, Clock3, FileCode2, ScanSearch, Tags, UploadCloud } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { isApiError } from '../api/client'
import { useParseGCode } from '../hooks/useParseGCode'
import { useUploadGCode } from '../hooks/useUploadGCode'
import { useCalculateGCodeWeight } from '../hooks/useCalculateGCodeWeight'
import { useDetectGCodeMaterial } from '../hooks/useDetectGCodeMaterial'
import { useEstimateGCodeTime } from '../hooks/useEstimateGCodeTime'
import { useMaterials } from '../hooks/useMaterials'
import {
  formatFileSize,
  GCODE_MAX_UPLOAD_BYTES,
  validateGCodeFile,
  type GCodeFileValidationError,
} from '../lib/gcodeUpload'
import { formatGCodeDuration } from '../lib/gcodeTime'

export function GCodeUploadPage() {
  const { i18n, t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [validationError, setValidationError] = useState<GCodeFileValidationError | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const upload = useUploadGCode()
  const parse = useParseGCode()

  const selectFile = (file: File | undefined) => {
    upload.reset()
    parse.reset()
    setIsDragging(false)
    if (!file) return

    const error = validateGCodeFile(file)
    setValidationError(error)
    setSelectedFile(error ? null : file)
  }

  const openFilePicker = () => inputRef.current?.click()
  const submitUpload = () => {
    if (!selectedFile || validationError || upload.isPending || upload.isSuccess) return
    upload.mutate(selectedFile)
  }
  const retryUpload = () => {
    if (!selectedFile || upload.isPending) return
    upload.mutate(selectedFile)
  }
  const analyzeUpload = () => {
    if (!upload.data || parse.isPending || parse.isSuccess) return
    parse.mutate(upload.data.upload_id)
  }
  const retryAnalysis = () => {
    if (!upload.data || parse.isPending) return
    parse.mutate(upload.data.upload_id)
  }
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    selectFile(event.dataTransfer.files[0])
  }

  const uploadError = upload.error
    ? isStorageQuotaError(upload.error)
      ? t('gcode.storageQuotaExceeded')
      : isApiError(upload.error) && upload.error.status === 413
      ? t('gcode.tooLarge')
      : t('gcode.uploadFailed')
    : null

  return (
    <section aria-labelledby="gcode-title" className="mx-auto w-full max-w-3xl">
      <header className="border-b border-line pb-5">
        <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">
          {t('gcode.eyebrow')}
        </p>
        <h2 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl" id="gcode-title">
          {t('gcode.title')}
        </h2>
        <p className="mt-2 text-sm leading-6 text-ink-muted sm:text-base">
          {t('gcode.description')}
        </p>
      </header>

      <div className="mt-7 rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-6">
        <div
          className={`rounded-xl border-2 border-dashed px-5 py-10 text-center transition-colors sm:px-8 sm:py-14 ${
            isDragging
              ? 'border-accent bg-accent/10'
              : 'border-line bg-surface-raised'
          }`}
          onDragEnter={(event) => {
            event.preventDefault()
            setIsDragging(true)
          }}
          onDragLeave={() => setIsDragging(false)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
        >
          <UploadCloud aria-hidden="true" className="mx-auto size-10 text-accent" strokeWidth={1.6} />
          <p className="mt-4 text-base font-semibold text-ink">{t('gcode.dropHere')}</p>
          <p className="mt-2 text-sm text-ink-muted">{t('gcode.or')}</p>
          <input
            accept=".gcode"
            aria-describedby="gcode-file-types"
            aria-label={t('gcode.selectFile')}
            className="sr-only"
            onChange={(event) => {
              selectFile(event.target.files?.[0])
              event.target.value = ''
            }}
            ref={inputRef}
            type="file"
          />
          <button
            className="mt-4 inline-flex min-h-12 items-center justify-center rounded-md bg-accent px-5 py-3 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            onClick={openFilePicker}
            type="button"
          >
            {t('gcode.selectFile')}
          </button>
          <p className="mt-4 text-xs text-ink-muted" id="gcode-file-types">
            {t('gcode.fileTypes', { size: formatFileSize(GCODE_MAX_UPLOAD_BYTES, i18n.resolvedLanguage ?? 'en') })}
          </p>
        </div>

        <div aria-live="polite">
          {validationError && (
            <div className="mt-5 flex items-start gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-800 dark:text-red-200" role="alert">
              <AlertCircle aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
              <span>{t(`gcode.${validationError}`)}</span>
            </div>
          )}

          {selectedFile && !upload.isSuccess && (
            <div className="mt-5 flex min-w-0 items-center gap-3 rounded-lg border border-line bg-surface-raised p-4">
              <FileCode2 aria-hidden="true" className="size-6 shrink-0 text-accent" />
              <div className="min-w-0">
                <p className="truncate font-semibold text-ink">{selectedFile.name}</p>
                <p className="mt-0.5 text-sm text-ink-muted">
                  {formatFileSize(selectedFile.size, i18n.resolvedLanguage ?? 'en')}
                </p>
              </div>
            </div>
          )}

          {uploadError && (
            <div className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-4" role="alert">
              <div className="flex items-start gap-3 text-sm text-red-800 dark:text-red-200">
                <AlertCircle aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
                <span>{uploadError}</span>
              </div>
              <button
                className="mt-4 min-h-11 rounded-md border border-red-500/40 bg-surface px-4 py-2 text-sm font-bold text-ink disabled:opacity-60"
                disabled={upload.isPending}
                onClick={retryUpload}
                type="button"
              >
                {t('gcode.tryAgain')}
              </button>
            </div>
          )}

          {upload.data && (
            <div
              className="mt-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-5"
              data-upload-id={upload.data.upload_id}
              role="status"
            >
              <div className="flex items-center gap-3 text-emerald-800 dark:text-emerald-200">
                <CheckCircle2 aria-hidden="true" className="size-6 shrink-0" />
                <h3 className="font-semibold">{t('gcode.success')}</h3>
              </div>
              <p className="mt-4 break-words font-semibold text-ink">{upload.data.filename}</p>
              <p className="mt-1 text-sm text-ink-muted">
                {formatFileSize(upload.data.size_bytes, i18n.resolvedLanguage ?? 'en')}
              </p>
              <p className="mt-4 text-sm font-medium text-ink">{t('gcode.ready')}</p>
              <button
                aria-busy={parse.isPending}
                className="mt-5 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-md bg-accent px-5 py-3 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50"
                disabled={parse.isPending || parse.isSuccess}
                onClick={analyzeUpload}
                type="button"
              >
                <ScanSearch aria-hidden="true" className="size-5" />
                {parse.isPending ? t('gcode.analyzing') : t('gcode.analyze')}
              </button>
            </div>
          )}

          {parse.error && (
            <div className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-4" role="alert">
              <div className="flex items-start gap-3 text-sm text-red-800 dark:text-red-200">
                <AlertCircle aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
                <span>{t('gcode.parseFailed')}</span>
              </div>
              <button
                className="mt-4 min-h-11 rounded-md border border-red-500/40 bg-surface px-4 py-2 text-sm font-bold text-ink disabled:opacity-60"
                disabled={parse.isPending}
                onClick={retryAnalysis}
                type="button"
              >
                {t('gcode.tryAgain')}
              </button>
            </div>
          )}

          {parse.data && (
            <GCodeAnalysisResults result={parse.data} uploadId={upload.data?.upload_id ?? ''} />
          )}
        </div>

        <button
          aria-busy={upload.isPending}
          className="mt-6 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-md bg-accent px-5 py-3 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!selectedFile || Boolean(validationError) || upload.isPending || upload.isSuccess}
          onClick={submitUpload}
          type="button"
        >
          <UploadCloud aria-hidden="true" className="size-5" />
          {upload.isPending ? t('gcode.uploading') : t('gcode.upload')}
        </button>
      </div>
    </section>
  )
}

function isStorageQuotaError(error: unknown): boolean {
  if (!isApiError(error)) return false
  const response = error.detail
  if (!response || typeof response !== 'object') return false
  const detail = 'detail' in response ? response.detail : response
  return Boolean(
    detail
    && typeof detail === 'object'
    && 'code' in detail
    && detail.code === 'gcode_storage_quota_exceeded',
  )
}

function GCodeAnalysisResults({ result, uploadId }: {
  result: import('../types/gcode').GCodeParseResult
  uploadId: string
}) {
  const materialDetection = useDetectGCodeMaterial(uploadId)

  return (
    <>
      <ParseSummary result={result} />
      <MaterialAnalysis
        isError={materialDetection.isError}
        isPending={materialDetection.isPending}
        result={materialDetection.data}
      />
      <WeightAnalysis detection={materialDetection.data} result={result} uploadId={uploadId} />
      <TimeAnalysis uploadId={uploadId} />
    </>
  )
}

function MaterialAnalysis({ isError, isPending, result }: {
  isError: boolean
  isPending: boolean
  result?: import('../types/gcode').GCodeMaterialDetectionResult
}) {
  const { t } = useTranslation()
  const tools = Array.isArray(result?.tools) ? result.tools : []

  return (
    <section aria-labelledby="gcode-material-title" className="mt-5 rounded-xl border border-line bg-surface-raised p-5 sm:p-6">
      <div className="flex items-center gap-3">
        <Tags aria-hidden="true" className="size-6 shrink-0 text-accent" />
        <h3 className="text-lg font-semibold text-ink" id="gcode-material-title">{t('gcode.material.title')}</h3>
      </div>

      {isPending && <p className="mt-5 text-sm text-ink-muted" role="status">{t('gcode.material.detecting')}</p>}
      {isError && <p className="mt-5 text-sm text-red-700 dark:text-red-200" role="alert">{t('gcode.material.failed')}</p>}
      {result && tools.length === 0 && <p className="mt-5 text-sm text-ink-muted">{t('gcode.material.notDetected')}</p>}

      {tools.length > 0 && (
        <div aria-label={t('gcode.material.result')} className="mt-5 space-y-3" role="region">
          {tools.map((tool) => {
            const label = tool.material_name ?? tool.raw_material_label
            const isLikely = tool.confidence === 'MEDIUM'
            const isDetected = tool.confidence === 'HIGH'
            return (
              <article className="rounded-lg border border-line bg-surface p-4" key={tool.tool}>
                <p className="font-mono text-sm font-bold text-ink">T{tool.tool}</p>
                <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  {isDetected
                    ? t('gcode.material.detected')
                    : isLikely
                      ? t('gcode.material.probable')
                      : t('gcode.material.notDetected')}
                </p>
                {label && <p className="mt-1 break-words text-xl font-bold text-ink">{label}</p>}

                {tool.confidence !== 'NONE' && (
                  <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="font-semibold text-ink-muted">{t('gcode.material.confidence')}</dt>
                      <dd className="font-semibold text-ink">{t(`gcode.material.confidence${tool.confidence}`)}</dd>
                    </div>
                    {tool.source && (
                      <div>
                        <dt className="font-semibold text-ink-muted">{t('gcode.material.source')}</dt>
                        <dd className="font-semibold text-ink">
                          {tool.source === 'slicer_metadata'
                            ? t('gcode.material.sourceMetadata')
                            : t('gcode.material.sourceTemperature')}
                        </dd>
                      </div>
                    )}
                  </dl>
                )}

                {tool.candidates.length > 0 && (
                  <div className="mt-3 text-sm">
                    <p className="font-semibold text-ink-muted">{t('gcode.material.candidates')}</p>
                    <p className="mt-1 text-ink">{tool.candidates.map((candidate) => candidate.material_name).join(', ')}</p>
                  </div>
                )}
                {tool.warnings.includes('explicit_material_not_in_catalog') && (
                  <p className="mt-3 text-sm text-amber-800 dark:text-amber-200">{t('gcode.material.catalogMissing')}</p>
                )}
                {(tool.confidence === 'LOW' || tool.warnings.includes('ambiguous_material')) && (
                  <p className="mt-3 text-sm text-amber-800 dark:text-amber-200">{t('gcode.material.ambiguous')}</p>
                )}
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}

const KINEMATIC_WARNING_KEYS = [
  'acceleration_not_modeled',
  'temperature_waits_not_modeled',
  'user_pause_not_modeled',
  'tool_change_overhead_not_modeled',
  'incomplete_kinematic_estimate',
  'arc_duration_approximated',
] as const

function TimeAnalysis({ uploadId }: { uploadId: string }) {
  const { i18n, t } = useTranslation()
  const time = useEstimateGCodeTime(uploadId)
  const result = time.data
  const visibleWarnings = result?.source === 'command_kinematics'
    ? KINEMATIC_WARNING_KEYS.filter((warning) => result.warnings.includes(warning))
    : []

  return (
    <section aria-labelledby="gcode-time-title" className="mt-5 rounded-xl border border-line bg-surface-raised p-5 sm:p-6">
      <div className="flex items-center gap-3">
        <Clock3 aria-hidden="true" className="size-6 shrink-0 text-accent" />
        <h3 className="text-lg font-semibold text-ink" id="gcode-time-title">{t('gcode.time.title')}</h3>
      </div>

      {time.isPending && <p className="mt-5 text-sm text-ink-muted" role="status">{t('gcode.time.calculating')}</p>}
      {time.isError && <p className="mt-5 text-sm text-red-700 dark:text-red-200" role="alert">{t('gcode.time.unavailable')}</p>}

      {result && (
        <div aria-label={t('gcode.time.result')} className="mt-5" role="region">
          <p className="text-3xl font-bold text-ink">
            {result.estimated_time_seconds === null
              ? '—'
              : `${result.is_heuristic ? '~' : ''}${formatGCodeDuration(result.estimated_time_seconds, i18n.resolvedLanguage ?? 'en')}`}
          </p>
          {result.source ? (
            <dl className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
              <dt className="font-semibold text-ink-muted">{t('gcode.time.source')}</dt>
              <dd className="font-semibold text-ink">
                {result.source === 'slicer_metadata'
                  ? t('gcode.time.slicerSource')
                  : t('gcode.time.calculatedSource')}
              </dd>
            </dl>
          ) : (
            <p className="mt-3 text-sm text-ink-muted">{t('gcode.time.unavailable')}</p>
          )}

          {visibleWarnings.length > 0 && (
            <ul className="mt-4 space-y-1 text-sm text-amber-800 dark:text-amber-200">
              {visibleWarnings.map((warning) => (
                <li key={warning}>{t(`gcode.time.warnings.${warning}`)}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}

interface ToolWeightInput {
  materialId: string
  diameter: string
}

function WeightAnalysis({ detection, result, uploadId }: {
  detection?: import('../types/gcode').GCodeMaterialDetectionResult
  result: import('../types/gcode').GCodeParseResult
  uploadId: string
}) {
  const { i18n, t } = useTranslation()
  const locale = i18n.resolvedLanguage ?? 'en'
  const materials = useMaterials()
  const weight = useCalculateGCodeWeight(uploadId)
  const materialOptions = Array.isArray(materials.data) ? materials.data : []
  const initialInputs = useMemo(
    () => Object.fromEntries(result.tools.map((tool) => [
      tool.tool,
      {
        materialId: '',
        diameter: tool.extrusion_length_mm === null
          ? ''
          : metadataPhysicalValue(result.metadata, ['filament_diameter_mm', 'filament_diameter'], tool.tool) ?? '1.75',
      },
    ])) as Record<number, ToolWeightInput>,
    [result],
  )
  const [inputs, setInputs] = useState<Record<number, ToolWeightInput>>(initialInputs)
  const manuallyEditedMaterials = useRef(new Set<number>())

  useEffect(() => {
    if (!Array.isArray(detection?.tools)) return
    setInputs((current) => {
      let changed = false
      const next = { ...current }
      for (const detected of detection.tools) {
        if (
          detected.confidence !== 'HIGH'
          || detected.material_id === null
          || manuallyEditedMaterials.current.has(detected.tool)
          || current[detected.tool]?.materialId
        ) continue
        next[detected.tool] = {
          ...current[detected.tool],
          materialId: String(detected.material_id),
        }
        changed = true
      }
      return changed ? next : current
    })
  }, [detection])

  const updateInput = (tool: number, field: keyof ToolWeightInput, value: string) => {
    if (field === 'materialId') manuallyEditedMaterials.current.add(tool)
    weight.reset()
    setInputs((current) => ({
      ...current,
      [tool]: { ...current[tool], [field]: value },
    }))
  }
  const invalidDiameter = result.tools.some((tool) => {
    if (tool.extrusion_length_mm === null) return false
    const value = Number(inputs[tool.tool]?.diameter)
    return !Number.isFinite(value) || value <= 0 || value > 20
  })
  const calculate = () => {
    if (weight.isPending || invalidDiameter) return
    weight.mutate({
      tools: result.tools.map((tool) => {
        const input = inputs[tool.tool]
        return {
          tool: tool.tool,
          ...(input?.materialId ? { material_id: Number(input.materialId) } : {}),
          ...(tool.extrusion_length_mm !== null && input?.diameter
            ? { filament_diameter_mm: input.diameter.trim() }
            : {}),
        }
      }),
    })
  }

  return (
    <section aria-labelledby="gcode-weight-title" className="mt-5 rounded-xl border border-line bg-surface-raised p-5 sm:p-6">
      <h3 className="text-lg font-semibold text-ink" id="gcode-weight-title">{t('gcode.weight.title')}</h3>
      <div className="mt-5 space-y-4">
        {result.tools.map((tool) => {
          const input = inputs[tool.tool]
          const selectedMaterial = materialOptions.find((item) => String(item.id) === input?.materialId)
          const volumetricOnly = tool.extrusion_length_mm === null && tool.extrusion_volume_mm3 !== null
          return (
            <fieldset className="rounded-lg border border-line bg-surface p-4" key={tool.tool}>
              <legend className="px-1 font-mono text-sm font-bold text-ink">T{tool.tool}</legend>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-semibold text-ink">
                  {t('gcode.weight.material')}
                  <select
                    aria-label={`${t('gcode.weight.material')} T${tool.tool}`}
                    className="mt-2 min-h-11 w-full rounded-md border border-line bg-surface-raised px-3 text-ink"
                    onChange={(event) => updateInput(tool.tool, 'materialId', event.target.value)}
                    value={input?.materialId ?? ''}
                  >
                    <option value="">{t('gcode.weight.selectMaterial')}</option>
                    {materialOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                {volumetricOnly ? (
                  <p className="self-end rounded-md bg-accent/10 p-3 text-sm text-ink-muted">
                    {t('gcode.weight.volumetric')}
                  </p>
                ) : (
                  <label className="text-sm font-semibold text-ink">
                    {t('gcode.weight.diameter')}
                    <span className="mt-2 flex items-center gap-2">
                      <input
                        aria-label={`${t('gcode.weight.diameter')} T${tool.tool}`}
                        className="min-h-11 min-w-0 flex-1 rounded-md border border-line bg-surface-raised px-3 text-ink"
                        inputMode="decimal"
                        max="20"
                        min="0.01"
                        onChange={(event) => updateInput(tool.tool, 'diameter', event.target.value)}
                        step="0.01"
                        type="number"
                        value={input?.diameter ?? ''}
                      />
                      <span className="text-sm text-ink-muted">mm</span>
                    </span>
                  </label>
                )}
              </div>
              {selectedMaterial && (
                <p className="mt-3 text-sm text-ink-muted">
                  {selectedMaterial.density_g_cm3 === null
                    ? t('gcode.weight.missingDensity')
                    : `${t('gcode.weight.density')}: ${formatDecimal(selectedMaterial.density_g_cm3, locale, 3)} g/cm³`}
                </p>
              )}
            </fieldset>
          )
        })}
      </div>

      {invalidDiameter && <p className="mt-4 text-sm text-red-700 dark:text-red-200" role="alert">{t('gcode.weight.missingDiameter')}</p>}
      {materials.isError && <p className="mt-4 text-sm text-red-700 dark:text-red-200" role="alert">{t('gcode.weight.materialsFailed')}</p>}
      {weight.isError && <p className="mt-4 text-sm text-red-700 dark:text-red-200" role="alert">{t('gcode.weight.calculateFailed')}</p>}

      <button
        aria-busy={weight.isPending}
        className="mt-5 min-h-12 w-full rounded-md bg-accent px-5 py-3 text-sm font-bold text-sidebar disabled:cursor-not-allowed disabled:opacity-50"
        disabled={weight.isPending || invalidDiameter}
        onClick={calculate}
        type="button"
      >
        {weight.isPending ? t('gcode.weight.calculating') : t('gcode.weight.calculate')}
      </button>

      {weight.data && <WeightResult result={weight.data} locale={locale} />}
    </section>
  )
}

function WeightResult({ result, locale }: {
  result: import('../types/gcode').GCodeWeightResult
  locale: string
}) {
  const { t } = useTranslation()
  const headline = result.is_complete
    ? result.total_estimated_weight_g
    : result.known_estimated_weight_g
  return (
    <section aria-label={t('gcode.weight.estimated')} className="mt-5 border-t border-line pt-5" aria-live="polite">
      <p className="text-sm font-semibold text-ink-muted">
        {result.is_complete ? t('gcode.weight.total') : t('gcode.weight.knownSubtotal')}
      </p>
      <p className="mt-1 text-3xl font-bold text-ink">
        {headline === null ? '—' : `${formatDecimal(headline, locale, 2)} g`}
      </p>
      <ul className="mt-4 space-y-2">
        {result.tools.map((tool) => (
          <li className="flex flex-wrap justify-between gap-3 text-sm" key={tool.tool}>
            <span className="font-semibold text-ink">T{tool.tool}{tool.material_name ? ` — ${tool.material_name}` : ''}</span>
            <span className="text-ink-muted">
              {tool.estimated_weight_g === null ? '—' : `${formatDecimal(tool.estimated_weight_g, locale, 2)} g`}
            </span>
          </li>
        ))}
      </ul>
      {!result.is_complete && <p className="mt-4 text-sm text-amber-800 dark:text-amber-200">{t('gcode.weight.incomplete')}</p>}
    </section>
  )
}

function metadataPhysicalValue(metadata: Record<string, string>, keys: string[], tool: number): string | null {
  const raw = keys.map((key) => metadata[key]).find(Boolean)
  if (!raw) return null
  const values = raw.split(',').map((value) => value.trim())
  const selected = values.length === 1 ? values[0] : values[tool]
  const numeric = Number(selected)
  return Number.isFinite(numeric) && numeric > 0 && numeric <= 20 ? selected : null
}

function formatDecimal(value: string | number, locale: string, digits: number): string {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(Number(value))
}

function ParseSummary({ result }: { result: import('../types/gcode').GCodeParseResult }) {
  const { i18n, t } = useTranslation()
  const locale = i18n.resolvedLanguage ?? 'en'
  const formatCount = (value: number) => new Intl.NumberFormat(locale).format(value)

  return (
    <section
      aria-label={t('gcode.analyzed')}
      className="mt-5 rounded-xl border border-accent/30 bg-surface-raised p-5 sm:p-6"
    >
      <div className="flex items-center gap-3">
        <CheckCircle2 aria-hidden="true" className="size-6 shrink-0 text-emerald-600 dark:text-emerald-300" />
        <h3 className="text-lg font-semibold text-ink">{t('gcode.analyzed')}</h3>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <SummaryMetric label={t('gcode.lines')} value={formatCount(result.line_count)} />
        <SummaryMetric label={t('gcode.commands')} value={formatCount(result.command_line_count)} />
        <SummaryMetric label={t('gcode.tools')} value={formatCount(result.tools.length)} />
        {result.total_extrusion_length_mm !== null && (
          <SummaryMetric
            label={t('gcode.extrusionLength')}
            value={formatExtrusionLength(result.total_extrusion_length_mm, locale)}
          />
        )}
        {result.total_extrusion_volume_mm3 !== null && (
          <SummaryMetric
            label={t('gcode.volumetricExtrusion')}
            value={`${formatMetricNumber(result.total_extrusion_volume_mm3, locale)} mm³`}
          />
        )}
      </dl>

      {result.tools.length > 1 && (
        <div className="mt-5 border-t border-line pt-4">
          <h4 className="text-sm font-semibold text-ink">{t('gcode.toolBreakdown')}</h4>
          <ul className="mt-3 space-y-2 text-sm text-ink-muted">
            {result.tools.map((tool) => (
              <li className="flex flex-wrap items-baseline justify-between gap-2" key={tool.tool}>
                <span className="font-mono font-bold text-ink">T{tool.tool}</span>
                <span>{formatToolExtrusion(tool, locale)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="mt-5 border-t border-line pt-4">
          <h4 className="text-sm font-semibold text-ink">{t('gcode.parseWarnings')}</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-800 dark:text-amber-200">
            {result.warnings.map((warning) => (
              <li key={warning}>
                {t(`gcode.warnings.${warning}`, { defaultValue: warning })}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-line bg-surface p-3">
      <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</dt>
      <dd className="mt-2 break-words text-lg font-bold text-ink">{value}</dd>
    </div>
  )
}

function formatMetricNumber(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value)
}

function formatExtrusionLength(valueMm: number, locale: string): string {
  return valueMm >= 1000
    ? `${formatMetricNumber(valueMm / 1000, locale)} m`
    : `${formatMetricNumber(valueMm, locale)} mm`
}

function formatToolExtrusion(
  tool: import('../types/gcode').GCodeToolSummary,
  locale: string,
): string {
  const metrics: string[] = []
  if (tool.extrusion_length_mm !== null) {
    metrics.push(formatExtrusionLength(tool.extrusion_length_mm, locale))
  }
  if (tool.extrusion_volume_mm3 !== null) {
    metrics.push(`${formatMetricNumber(tool.extrusion_volume_mm3, locale)} mm³`)
  }
  return metrics.join(' · ') || '—'
}
