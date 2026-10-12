import {
  Activity,
  AlertCircle,
  Clock3,
  Droplets,
  Layers3,
  RefreshCw,
  Thermometer,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useBambuStatus } from '../hooks/useBambuStatus'
import type { BambuAmsTray, BambuPrintState } from '../types/bambu'

const activeStates = new Set<BambuPrintState>(['PREPARING', 'PRINTING', 'PAUSED'])

export function PrinterStatusPage() {
  const { i18n, t } = useTranslation()
  const { data, error, isFetching, isPending, refetch } = useBambuStatus()

  if (isPending) {
    return (
      <section aria-labelledby="printer-status-title">
        <PageHeading />
        <div aria-label={t('printerStatus.loading')} className="grid animate-pulse gap-5 lg:grid-cols-2">
          <div className="h-48 rounded-lg border border-line bg-surface" />
          <div className="h-48 rounded-lg border border-line bg-surface" />
        </div>
      </section>
    )
  }

  if (error || !data) {
    return (
      <section aria-labelledby="printer-status-title">
        <PageHeading />
        <div className="rounded-lg border border-red-500/30 bg-surface px-5 py-10 text-center shadow-sm" role="alert">
          <AlertCircle aria-hidden="true" className="mx-auto size-8 text-red-500" />
          <h3 className="mt-4 text-lg font-semibold text-ink">{t('printerStatus.loadError')}</h3>
          <p className="mt-2 text-sm text-ink-muted">{t('printerStatus.loadErrorDescription')}</p>
          <button
            className="mt-5 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar disabled:opacity-60"
            disabled={isFetching}
            onClick={() => void refetch()}
            type="button"
          >
            {isFetching ? t('printerStatus.refreshing') : t('common.retry')}
          </button>
        </div>
      </section>
    )
  }

  const progress = data.progress === null ? null : Math.min(100, Math.max(0, data.progress))
  const hasActivePrint = activeStates.has(data.state)
  const hasPrintTelemetry = hasActivePrint
    || Boolean(data.current_print)
    || Boolean(data.gcode_file)
    || data.progress !== null
    || data.current_layer !== null

  return (
    <section aria-labelledby="printer-status-title">
      <PageHeading />

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface px-4 py-3 shadow-sm">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className={`size-2.5 rounded-full ${data.connected ? 'bg-emerald-500 shadow-[0_0_0_4px_rgb(16_185_129/0.12)]' : 'bg-red-500 shadow-[0_0_0_4px_rgb(239_68_68/0.12)]'}`}
          />
          <div>
            <p className="font-semibold text-ink">
              {data.connected ? t('printerStatus.connected') : t('printerStatus.disconnected')}
            </p>
            <p className="text-xs text-ink-muted">
              {data.serial ?? t('printerStatus.serialUnavailable')}
              {' · '}
              {data.last_update_at
                ? t('printerStatus.lastUpdate', { value: formatTimestamp(data.last_update_at, i18n.resolvedLanguage) })
                : t('printerStatus.waitingForData')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-full border border-line px-2.5 py-1 font-mono text-[0.65rem] uppercase tracking-[0.14em] text-ink-muted">
            {t('printerStatus.readOnly')}
          </span>
          <button
            aria-label={t('printerStatus.refresh')}
            className="grid size-10 place-items-center rounded-md border border-line text-ink-muted transition-colors hover:border-accent/50 hover:text-accent disabled:opacity-50"
            disabled={isFetching}
            onClick={() => void refetch()}
            type="button"
          >
            <RefreshCw aria-hidden="true" className={`size-4 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {!data.configured && (
        <div className="mb-5 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-ink" role="status">
          <strong>{t('printerStatus.notConfigured')}</strong>{' '}
          {data.configuration_error ?? data.missing_configuration.join(', ')}
        </div>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <article className="rounded-lg border border-line bg-surface p-5 shadow-sm" aria-labelledby="connection-title">
          <div className="flex items-center gap-3">
            <span className={`rounded-md p-2 ${data.connected ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'bg-red-500/10 text-red-600 dark:text-red-400'}`}>
              {data.connected ? <Wifi aria-hidden="true" className="size-5" /> : <WifiOff aria-hidden="true" className="size-5" />}
            </span>
            <div>
              <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-ink-muted">P1S / MQTT</p>
              <h3 className="text-lg font-semibold text-ink" id="connection-title">{t('printerStatus.connection')}</h3>
            </div>
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5 text-sm">
            <StatusField label={t('printerStatus.connectionState')} value={t(`printerStatus.connections.${data.connection_state}`)} />
            <StatusField label={t('printerStatus.serial')} value={data.serial} />
            <StatusField label={t('printerStatus.normalizedState')} value={t(`printerStatus.states.${data.state}`)} />
            <StatusField label={t('printerStatus.rawState')} value={data.raw_state} />
            <StatusField label={t('printerStatus.ftps')} value={!data.ftps_configured ? t('printerStatus.ftpsStates.unconfigured') : data.ftps_reachable === true ? t('printerStatus.ftpsStates.reachable') : data.ftps_reachable === false ? t('printerStatus.ftpsStates.error') : t('printerStatus.ftpsStates.waiting')} />
            <StatusField label={t('printerStatus.lastFtpsSuccess')} value={data.last_ftps_success_at ? formatTimestamp(data.last_ftps_success_at, i18n.resolvedLanguage) : null} />
          </dl>
        </article>

        <article className="rounded-lg border border-line bg-surface p-5 shadow-sm" aria-labelledby="current-print-title">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="rounded-md bg-accent-soft p-2 text-accent"><Activity aria-hidden="true" className="size-5" /></span>
              <div>
                <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-ink-muted">LIVE</p>
                <h3 className="text-lg font-semibold text-ink" id="current-print-title">{t('printerStatus.currentPrint')}</h3>
              </div>
            </div>
            <span className={stateBadgeClass(data.state)}>{t(`printerStatus.states.${data.state}`)}</span>
          </div>

          {hasPrintTelemetry ? (
            <>
              <p className="mt-5 truncate text-base font-semibold text-ink">{data.current_print ?? data.project_name ?? data.gcode_file ?? t('printerStatus.unnamedPrint')}</p>
              {data.gcode_file && <p className="mt-1 truncate font-mono text-xs text-ink-muted">{data.gcode_file}</p>}
              <div className="mt-5">
                <div className="mb-2 flex justify-between text-sm">
                  <span className="text-ink-muted">{t('printerStatus.progress')}</span>
                  <strong className="font-mono text-ink">{progress === null ? '—' : `${progress}%`}</strong>
                </div>
                <div aria-label={t('printerStatus.progress')} aria-valuemax={100} aria-valuemin={0} aria-valuenow={progress ?? undefined} className="h-2 overflow-hidden rounded-full bg-line" role="progressbar">
                  <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${progress ?? 0}%` }} />
                </div>
              </div>
              <dl className="mt-5 grid grid-cols-2 gap-4 text-sm">
                <IconField icon={Layers3} label={t('printerStatus.layer')} value={formatLayer(data.current_layer, data.total_layers)} />
                <IconField icon={Clock3} label={t('printerStatus.remaining')} value={formatMinutes(data.remaining_time_minutes, t('printerStatus.minutes'))} />
                <StatusField label={t('printerStatus.taskId')} value={data.task_id} />
                <StatusField label={t('printerStatus.subtaskId')} value={data.subtask_id} />
              </dl>
              {data.active_print_job_id !== null && (
                <Link className="mt-5 inline-flex text-sm font-semibold text-accent hover:underline" to={`/prints/${data.active_print_job_id}`}>
                  {t('printerStatus.openHistory', { id: data.active_print_job_id })}
                </Link>
              )}
            </>
          ) : (
            <div className="mt-5 rounded-md border border-dashed border-line px-4 py-7 text-center">
              <p className="font-semibold text-ink">{t('printerStatus.noActivePrint')}</p>
              <p className="mt-1 text-sm text-ink-muted">{t('printerStatus.noActivePrintDescription')}</p>
            </div>
          )}
        </article>
      </div>

      <section aria-labelledby="ams-title" className="mt-5 rounded-lg border border-line bg-surface p-5 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-ink-muted">AMS</p>
            <h3 className="mt-1 text-lg font-semibold text-ink" id="ams-title">{t('printerStatus.ams')}</h3>
          </div>
          <p className="text-xs text-ink-muted">{t('printerStatus.autoRefresh')}</p>
        </div>

        {data.ams.length === 0 && !data.external_tray ? (
          <p className="mt-5 rounded-md border border-dashed border-line px-4 py-7 text-center text-sm text-ink-muted">{t('printerStatus.noAms')}</p>
        ) : (
          <div className="mt-5 space-y-5">
            {data.ams.map((unit) => (
              <div key={unit.unit_id}>
                <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                  <strong className="text-ink">{t('printerStatus.amsUnit', { id: unit.unit_id })}</strong>
                  {unit.humidity !== null && <span className="inline-flex items-center gap-1 text-ink-muted"><Droplets aria-hidden="true" className="size-3.5" />{unit.humidity}</span>}
                  {unit.temperature_c !== null && <span className="inline-flex items-center gap-1 text-ink-muted"><Thermometer aria-hidden="true" className="size-3.5" />{unit.temperature_c} °C</span>}
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {unit.trays.map((tray) => <TrayCard current={data.current_tray === tray.tray_id} key={tray.tray_id} tray={tray} />)}
                </div>
              </div>
            ))}
            {data.external_tray && (
              <div className="max-w-sm">
                <strong className="mb-3 block text-sm text-ink">{t('printerStatus.externalTray')}</strong>
                <TrayCard current={data.current_tray === data.external_tray.tray_id} tray={data.external_tray} />
              </div>
            )}
          </div>
        )}
      </section>
    </section>
  )
}

function PageHeading() {
  const { t } = useTranslation()
  return (
    <div className="mb-6">
      <div className="mb-3 flex items-center gap-3">
        <span aria-hidden="true" className="h-px w-8 bg-accent" />
        <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">{t('printerStatus.eyebrow')}</p>
      </div>
      <h2 className="text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl" id="printer-status-title">{t('printerStatus.title')}</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-ink-muted sm:text-base">{t('printerStatus.description')}</p>
    </div>
  )
}

function StatusField({ label, value }: { label: string; value: string | null }) {
  const { t } = useTranslation()
  return (
    <div>
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="mt-1 break-all font-medium text-ink">{value || t('printerStatus.unavailable')}</dd>
    </div>
  )
}

function IconField({ icon: Icon, label, value }: { icon: typeof Layers3; label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-accent" />
      <div><dt className="text-xs text-ink-muted">{label}</dt><dd className="mt-1 font-medium text-ink">{value}</dd></div>
    </div>
  )
}

function TrayCard({ current, tray }: { current: boolean; tray: BambuAmsTray }) {
  const { t } = useTranslation()
  const color = trayColor(tray.color)
  return (
    <article className={`rounded-md border p-4 ${current ? 'border-accent bg-accent-soft/50' : 'border-line bg-canvas/40'}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span aria-hidden="true" className="size-5 shrink-0 rounded-full border border-black/10 shadow-sm" style={{ backgroundColor: color ?? 'transparent' }} />
          <strong className="truncate text-sm text-ink">{t('printerStatus.tray', { id: tray.tray_id })}</strong>
        </div>
        {current && <span className="rounded-full bg-accent px-2 py-0.5 text-[0.62rem] font-bold uppercase tracking-wide text-white">{t('printerStatus.selected')}</span>}
      </div>
      <p className="mt-3 font-semibold text-ink">{[tray.brand, tray.material_type].filter(Boolean).join(' · ') || t('printerStatus.emptyTray')}</p>
      <p className="mt-1 text-xs text-ink-muted">
        {tray.profile_id ?? t('printerStatus.profileUnavailable')}
        {tray.remaining_percent !== null && tray.remaining_percent >= 0 ? ` · ${tray.remaining_percent}%` : ''}
      </p>
    </article>
  )
}

function stateBadgeClass(state: BambuPrintState): string {
  const tone = state === 'PRINTING'
    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
    : state === 'PAUSED' || state === 'PREPARING'
      ? 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300'
      : state === 'FAILED' || state === 'CANCELLED'
        ? 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300'
        : 'border-line bg-canvas text-ink-muted'
  return `rounded-full border px-2.5 py-1 text-xs font-semibold ${tone}`
}

function trayColor(value: string | null): string | null {
  if (!value) return null
  const normalized = value.replace(/^#/, '').slice(0, 6)
  return /^[0-9a-f]{6}$/i.test(normalized) ? `#${normalized}` : null
}

function formatLayer(current: number | null, total: number | null): string {
  if (current === null && total === null) return '—'
  if (total === null) return String(current)
  return `${current ?? '—'} / ${total}`
}

function formatMinutes(value: number | null, suffix: string): string {
  return value === null ? '—' : `${value} ${suffix}`
}

function formatTimestamp(value: string, language: string | undefined): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(language === 'en' ? 'en' : 'pt-BR', {
    dateStyle: 'short',
    timeStyle: 'medium',
  }).format(parsed)
}
