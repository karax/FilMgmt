import {
  AlertCircle,
  Boxes,
  CheckCircle2,
  CircleDollarSign,
  Download,
  PackageCheck,
  Scale,
  Sparkles,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { HighlightCard, KpiCard } from '../components/analytics/AnalyticsCards'
import {
  ActivityLineChart,
  ConsumptionLineChart,
  DimensionBarChart,
  InventoryBarChart,
  PrintOutcomesChart,
  PurchaseLineChart,
  StoreBarChart,
  TopSpoolsChart,
} from '../components/analytics/AnalyticsCharts'
import { AnalyticsPanel } from '../components/analytics/AnalyticsPanel'
import { AnalyticsSkeleton } from '../components/analytics/AnalyticsSkeleton'
import { AnalyticsExportDialog } from '../components/analytics/AnalyticsExportDialog'
import {
  useAnalyticsDashboard,
  useConsumptionByBrand,
  useConsumptionByMaterial,
  useConsumptionSeries,
  useInventoryByMaterial,
  usePrintActivity,
  usePurchaseSpendSeries,
  usePurchasesByStore,
  useTopConsumingPrints,
  useTopSpools,
} from '../hooks/useAnalytics'
import {
  analyticsTimezone,
  asNumber,
  bucketForRange,
  formatCurrency,
  formatDuration,
  formatGrams,
  formatPercentage,
} from '../lib/analytics'
import type { AnalyticsFilters, AnalyticsRangePreset } from '../types/analytics'

const rangePresets: AnalyticsRangePreset[] = [
  'last_7_days',
  'last_30_days',
  'last_90_days',
  'this_year',
  'last_12_months',
  'all_time',
  'custom',
]

function isRangePreset(value: string | null): value is AnalyticsRangePreset {
  return rangePresets.includes(value as AnalyticsRangePreset)
}

export function AnalyticsPage() {
  const { t, i18n } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [storeMode, setStoreMode] = useState<'spend' | 'count'>('spend')
  const [exportOpen, setExportOpen] = useState(false)
  const [exportedFilename, setExportedFilename] = useState<string | null>(null)
  const rangeParam = searchParams.get('range')
  const range: AnalyticsRangePreset = isRangePreset(rangeParam) ? rangeParam : 'last_30_days'
  const from = searchParams.get('from') ?? undefined
  const to = searchParams.get('to') ?? undefined
  const locale = i18n.resolvedLanguage ?? i18n.language
  const filters = useMemo<AnalyticsFilters>(() => ({ range, from, to, timezone: analyticsTimezone() }), [from, range, to])
  const bucket = bucketForRange(range)

  const dashboard = useAnalyticsDashboard(filters)
  const consumption = useConsumptionSeries(filters, bucket)
  const topSpools = useTopSpools(filters)
  const materials = useConsumptionByMaterial(filters)
  const brands = useConsumptionByBrand(filters)
  const inventory = useInventoryByMaterial(filters)
  const stores = usePurchasesByStore(filters)
  const purchaseSeries = usePurchaseSpendSeries(filters, bucket)
  const printActivity = usePrintActivity(filters, bucket)
  const topPrints = useTopConsumingPrints(filters)

  function setRange(nextRange: AnalyticsRangePreset) {
    const next = new URLSearchParams(searchParams)
    next.set('range', nextRange)
    if (nextRange !== 'custom') {
      next.delete('from')
      next.delete('to')
    }
    setSearchParams(next)
  }

  function setCustomDate(key: 'from' | 'to', value: string) {
    const next = new URLSearchParams(searchParams)
    next.set('range', 'custom')
    if (value) next.set(key, value)
    else next.delete(key)
    setSearchParams(next, { replace: true })
  }

  return (
    <section aria-labelledby="analytics-title">
      <header className="mb-6 gap-5 lg:flex lg:items-end lg:justify-between">
        <div>
          <div className="mb-3 flex items-center gap-3">
            <span aria-hidden="true" className="h-px w-8 bg-accent" />
            <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">{t('analytics.eyebrow')}</p>
          </div>
          <h2 className="text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl" id="analytics-title">{t('analytics.title')}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted sm:text-base">{t('analytics.description')}</p>
        </div>
        <div className="mt-5 flex flex-wrap items-end gap-2 lg:mt-0">
          <button className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-surface px-3 text-sm font-semibold text-ink shadow-sm hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onClick={() => { setExportedFilename(null); setExportOpen(true) }} type="button"><Download aria-hidden="true" className="size-4" />{t('analytics.export.open')}</button>
          <label className="min-w-44 flex-1 lg:flex-none">
            <span className="mb-1.5 block text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-ink-muted">{t('analytics.range.label')}</span>
            <select aria-label={t('analytics.range.label')} className="h-10 w-full rounded-md border border-line bg-surface px-3 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onChange={(event) => setRange(event.target.value as AnalyticsRangePreset)} value={range}>
              {rangePresets.map((preset) => <option key={preset} value={preset}>{t(`analytics.range.${preset}`)}</option>)}
            </select>
          </label>
          {range === 'custom' && (
            <>
              <label><span className="mb-1.5 block text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-ink-muted">{t('analytics.range.from')}</span><input aria-label={t('analytics.range.from')} className="h-10 rounded-md border border-line bg-surface px-3 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" max={to} onChange={(event) => setCustomDate('from', event.target.value)} type="date" value={from ?? ''} /></label>
              <label><span className="mb-1.5 block text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-ink-muted">{t('analytics.range.to')}</span><input aria-label={t('analytics.range.to')} className="h-10 rounded-md border border-line bg-surface px-3 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" min={from} onChange={(event) => setCustomDate('to', event.target.value)} type="date" value={to ?? ''} /></label>
            </>
          )}
        </div>
      </header>

      {exportedFilename && <div className="mb-5 rounded-lg border border-accent/25 bg-accent-soft px-4 py-3 text-sm text-ink" role="status">{t('analytics.export.downloaded', { filename: exportedFilename })}</div>}

      {range === 'custom' && (!from || !to) ? (
        <div className="rounded-xl border border-dashed border-line bg-surface px-6 py-14 text-center text-sm text-ink-muted">{t('analytics.range.chooseDates')}</div>
      ) : dashboard.isPending ? (
        <AnalyticsSkeleton />
      ) : dashboard.error || !dashboard.data ? (
        <FatalError isFetching={dashboard.isFetching} onRetry={() => void dashboard.refetch()} />
      ) : (
        <AnalyticsDashboardContent
          brands={brands}
          consumption={consumption}
          dashboard={dashboard.data}
          inventory={inventory}
          locale={locale}
          materials={materials}
          printActivity={printActivity}
          purchaseSeries={purchaseSeries}
          storeMode={storeMode}
          stores={stores}
          topPrints={topPrints}
          topSpools={topSpools}
          onStoreModeChange={setStoreMode}
        />
      )}
      {exportOpen && <AnalyticsExportDialog bucket={bucket} filters={filters} onClose={() => setExportOpen(false)} onDownloaded={(filename) => { setExportedFilename(filename); setExportOpen(false) }} />}
    </section>
  )
}

type QueryResult<T> = { data?: T; error: unknown; isPending: boolean; refetch: () => Promise<unknown> }

function AnalyticsDashboardContent({ dashboard, locale, consumption, topSpools, materials, brands, inventory, stores, purchaseSeries, printActivity, topPrints, storeMode, onStoreModeChange }: {
  dashboard: NonNullable<ReturnType<typeof useAnalyticsDashboard>['data']>
  locale: string
  consumption: QueryResult<NonNullable<ReturnType<typeof useConsumptionSeries>['data']>>
  topSpools: QueryResult<NonNullable<ReturnType<typeof useTopSpools>['data']>>
  materials: QueryResult<NonNullable<ReturnType<typeof useConsumptionByMaterial>['data']>>
  brands: QueryResult<NonNullable<ReturnType<typeof useConsumptionByBrand>['data']>>
  inventory: QueryResult<NonNullable<ReturnType<typeof useInventoryByMaterial>['data']>>
  stores: QueryResult<NonNullable<ReturnType<typeof usePurchasesByStore>['data']>>
  purchaseSeries: QueryResult<NonNullable<ReturnType<typeof usePurchaseSpendSeries>['data']>>
  printActivity: QueryResult<NonNullable<ReturnType<typeof usePrintActivity>['data']>>
  topPrints: QueryResult<NonNullable<ReturnType<typeof useTopConsumingPrints>['data']>>
  storeMode: 'spend' | 'count'
  onStoreModeChange: (mode: 'spend' | 'count') => void
}) {
  const { t } = useTranslation()
  const cost = dashboard.consumption.estimated_costs
  const costValue = cost.length === 1 ? formatCurrency(cost[0].amount, cost[0].currency, locale) : cost.length > 1 ? t('analytics.multipleCurrencies', { count: cost.length }) : t('analytics.unavailable')
  const spendHighlight = dashboard.highlights.highest_spend_stores_by_currency
  const topStore = spendHighlight.length === 1 ? spendHighlight[0] : null

  return (
    <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <KpiCard icon={Scale} subtitle={t('analytics.periodValue', { range: t(`analytics.range.${dashboard.period.preset}`) })} title={t('analytics.kpi.consumed')} value={formatGrams(dashboard.consumption.confirmed_g, locale)} />
        <KpiCard icon={CircleDollarSign} subtitle={t('analytics.coverageValue', { value: formatPercentage(dashboard.consumption.cost_coverage_percentage, locale) })} title={t('analytics.kpi.materialCost')} value={costValue} />
        <KpiCard icon={Boxes} subtitle={t('analytics.activeSpools', { count: dashboard.inventory.active_spool_count })} title={t('analytics.kpi.currentInventory')} value={formatGrams(dashboard.inventory.current_remaining_g, locale)} />
        <KpiCard icon={CheckCircle2} subtitle={t('analytics.periodValue', { range: t(`analytics.range.${dashboard.period.preset}`) })} title={t('analytics.kpi.completed')} value={new Intl.NumberFormat(locale).format(dashboard.printing.completed)} />
        <KpiCard icon={PackageCheck} subtitle={t('analytics.terminalOnly')} title={t('analytics.kpi.successRate')} value={formatPercentage(dashboard.printing.success_rate_percentage, locale)} />
        <KpiCard icon={AlertCircle} subtitle={t('analytics.pendingUsages', { count: dashboard.reconciliation.pending_filament_usage_count })} title={t('analytics.kpi.pending')} tone={dashboard.reconciliation.pending_print_count > 0 ? 'attention' : 'default'} to="/reconciliation" value={new Intl.NumberFormat(locale).format(dashboard.reconciliation.pending_print_count)} />
      </div>

      <section aria-labelledby="analytics-highlights" className="mt-7">
        <SectionHeading id="analytics-highlights" title={t('analytics.sections.highlights')} />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <HighlightCard detail={dashboard.highlights.most_used_spool ? `${dashboard.highlights.most_used_spool.display_name} · ${formatGrams(dashboard.highlights.most_used_spool.consumption_g, locale)}` : t('analytics.noData')} title={t('analytics.highlights.spool')} to={dashboard.highlights.most_used_spool ? `/spools/${encodeURIComponent(dashboard.highlights.most_used_spool.code)}` : undefined} value={dashboard.highlights.most_used_spool?.code ?? '—'} />
          <HighlightCard detail={dashboard.highlights.most_consumed_material ? formatGrams(dashboard.highlights.most_consumed_material.consumption_g, locale) : t('analytics.noData')} title={t('analytics.highlights.material')} value={dashboard.highlights.most_consumed_material?.name ?? '—'} />
          <HighlightCard detail={dashboard.highlights.most_consumed_brand ? formatGrams(dashboard.highlights.most_consumed_brand.consumption_g, locale) : t('analytics.noData')} title={t('analytics.highlights.brand')} value={dashboard.highlights.most_consumed_brand?.name ?? '—'} />
          <HighlightCard detail={topStore ? formatCurrency(topStore.amount, topStore.currency, locale) : spendHighlight.length > 1 ? t('analytics.multipleCurrencies', { count: spendHighlight.length }) : t('analytics.noData')} title={t('analytics.highlights.spendStore')} value={topStore?.store ?? '—'} />
          <HighlightCard detail={dashboard.highlights.most_spools_store ? t('analytics.spoolCount', { count: dashboard.highlights.most_spools_store.spool_count }) : t('analytics.noData')} title={t('analytics.highlights.spoolsStore')} value={dashboard.highlights.most_spools_store?.store ?? '—'} />
        </div>
      </section>

      <section aria-labelledby="analytics-consumption" className="mt-8">
        <SectionHeading id="analytics-consumption" title={t('analytics.sections.consumption')} />
        <div className="grid gap-6 xl:grid-cols-2">
          <AnalyticsPanel className="xl:col-span-2" emptyMessage={t('analytics.empty.consumption')} error={consumption.error} isEmpty={!consumption.data?.points.length} isLoading={consumption.isPending} onRetry={() => void consumption.refetch()} subtitle={t('analytics.chartSubtitles.confirmed')} title={t('analytics.charts.consumption')}>
            {consumption.data && <ConsumptionLineChart bucket={consumption.data.bucket} label={t('analytics.charts.consumption')} locale={locale} points={consumption.data.points} />}
          </AnalyticsPanel>
          <AnalyticsPanel emptyMessage={t('analytics.empty.consumption')} error={topSpools.error} isEmpty={!topSpools.data?.length} isLoading={topSpools.isPending} onRetry={() => void topSpools.refetch()} subtitle={t('analytics.chartSubtitles.physicalSpools')} title={t('analytics.charts.topSpools')}>
            {topSpools.data && <TopSpoolsChart data={topSpools.data} label={t('analytics.charts.topSpools')} locale={locale} />}
          </AnalyticsPanel>
          <AnalyticsPanel emptyMessage={t('analytics.empty.consumption')} error={materials.error} isEmpty={!materials.data?.length} isLoading={materials.isPending} onRetry={() => void materials.refetch()} title={t('analytics.charts.material')}>
            {materials.data && <DimensionBarChart data={materials.data} label={t('analytics.charts.material')} locale={locale} />}
          </AnalyticsPanel>
          <AnalyticsPanel emptyMessage={t('analytics.empty.consumption')} error={brands.error} isEmpty={!brands.data?.length} isLoading={brands.isPending} onRetry={() => void brands.refetch()} title={t('analytics.charts.brand')}>
            {brands.data && <DimensionBarChart data={brands.data} label={t('analytics.charts.brand')} locale={locale} />}
          </AnalyticsPanel>
        </div>
      </section>

      <section aria-labelledby="analytics-inventory" className="mt-8">
        <SectionHeading id="analytics-inventory" title={t('analytics.sections.inventory')} />
        <AnalyticsPanel emptyMessage={t('analytics.empty.inventory')} error={inventory.error} isEmpty={!inventory.data?.length} isLoading={inventory.isPending} onRetry={() => void inventory.refetch()} subtitle={t('analytics.chartSubtitles.currentSnapshot')} title={t('analytics.charts.inventory')}>
          {inventory.data && <InventoryBarChart data={inventory.data} label={t('analytics.charts.inventory')} locale={locale} />}
        </AnalyticsPanel>
      </section>

      <section aria-labelledby="analytics-purchases" className="mt-8">
        <SectionHeading id="analytics-purchases" title={t('analytics.sections.purchases')} />
        <div className="grid gap-6 xl:grid-cols-2">
          <AnalyticsPanel action={<SegmentedControl mode={storeMode} onChange={onStoreModeChange} />} emptyMessage={t('analytics.empty.purchases')} error={stores.error} isEmpty={storeMode === 'spend' ? !stores.data?.by_spend.length : !stores.data?.by_spool_count.length} isLoading={stores.isPending} onRetry={() => void stores.refetch()} title={t('analytics.charts.stores')}>
            {stores.data && <StoreBarChart count={stores.data.by_spool_count} label={t('analytics.charts.stores')} locale={locale} mode={storeMode} spend={stores.data.by_spend} />}
          </AnalyticsPanel>
          <AnalyticsPanel emptyMessage={t('analytics.empty.purchases')} error={purchaseSeries.error} isEmpty={!purchaseSeries.data?.points.length} isLoading={purchaseSeries.isPending} onRetry={() => void purchaseSeries.refetch()} subtitle={t('analytics.chartSubtitles.currencySafe')} title={t('analytics.charts.purchaseSpend')}>
            {purchaseSeries.data && <PurchaseLineChart label={t('analytics.charts.purchaseSpend')} locale={locale} series={purchaseSeries.data} />}
          </AnalyticsPanel>
        </div>
      </section>

      <section aria-labelledby="analytics-printing" className="mt-8">
        <SectionHeading id="analytics-printing" title={t('analytics.sections.printing')} />
        <div className="grid gap-6 xl:grid-cols-2">
          <AnalyticsPanel emptyMessage={t('analytics.empty.prints')} error={printActivity.error} isEmpty={printActivity.data ? [printActivity.data.outcomes.completed, printActivity.data.outcomes.failed, printActivity.data.outcomes.cancelled, printActivity.data.outcomes.unknown_terminal].every((value) => value === 0) : true} isLoading={printActivity.isPending} onRetry={() => void printActivity.refetch()} subtitle={t('analytics.successValue', { value: formatPercentage(printActivity.data?.outcomes.success_rate_percentage ?? null, locale) })} title={t('analytics.charts.outcomes')}>
            {printActivity.data && <PrintOutcomesChart activity={printActivity.data} label={t('analytics.charts.outcomes')} labels={{ completed: t('analytics.outcomes.completed'), failed: t('analytics.outcomes.failed'), cancelled: t('analytics.outcomes.cancelled'), unknown: t('analytics.outcomes.unknown') }} />}
          </AnalyticsPanel>
          <AnalyticsPanel emptyMessage={t('analytics.empty.activity')} error={printActivity.error} isEmpty={!printActivity.data?.printing_seconds_by_period.length || printActivity.data.activity.actual_printing_seconds === 0} isLoading={printActivity.isPending} onRetry={() => void printActivity.refetch()} subtitle={t('analytics.observedWithCoverage', { duration: formatDuration(printActivity.data?.activity.actual_printing_seconds ?? 0, locale), coverage: formatPercentage(printActivity.data?.activity.duration_coverage_percentage ?? null, locale) })} title={t('analytics.charts.activity')}>
            {printActivity.data && <ActivityLineChart activity={printActivity.data} label={t('analytics.charts.activity')} locale={locale} />}
          </AnalyticsPanel>
          <AnalyticsPanel className="xl:col-span-2" emptyMessage={t('analytics.empty.consumption')} error={topPrints.error} isEmpty={!topPrints.data?.length} isLoading={topPrints.isPending} onRetry={() => void topPrints.refetch()} title={t('analytics.charts.largestPrints')}>
            {topPrints.data && <ol className="divide-y divide-line">{topPrints.data.map((item, index) => <li className="flex items-center gap-3 py-3 first:pt-0 last:pb-0" key={item.print_job_id}><span className="w-6 font-mono text-xs text-ink-muted">{index + 1}</span><Link className="min-w-0 flex-1 truncate text-sm font-semibold text-ink hover:text-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" to={`/prints/${item.print_job_id}`}>{item.name}</Link><span className="shrink-0 font-mono text-xs text-ink-muted">{formatGrams(item.consumption_g, locale)}</span></li>)}</ol>}
          </AnalyticsPanel>
        </div>
      </section>

      <section aria-labelledby="analytics-coverage" className="mt-8 rounded-xl border border-line bg-surface p-5 shadow-sm">
        <div className="flex items-center gap-2"><Sparkles aria-hidden="true" className="size-4 text-accent" /><h3 className="font-semibold text-ink" id="analytics-coverage">{t('analytics.sections.coverage')}</h3></div>
        <p className="mt-1 text-xs leading-5 text-ink-muted">{t('analytics.coverageDescription')}</p>
        <dl className="mt-5 grid gap-3 sm:grid-cols-3">
          <CoverageItem label={t('analytics.coverage.cost')} value={formatPercentage(dashboard.consumption.cost_coverage_percentage, locale)} />
          <CoverageItem help={dashboard.printing.duration_coverage_percentage !== null && asNumber(dashboard.printing.duration_coverage_percentage) < 100 ? t('analytics.durationHelp') : undefined} label={t('analytics.coverage.duration')} value={formatPercentage(dashboard.printing.duration_coverage_percentage, locale)} />
          <CoverageItem label={t('analytics.coverage.pending')} to="/reconciliation" value={t('analytics.pendingPrints', { count: dashboard.reconciliation.pending_print_count })} />
        </dl>
      </section>
    </>
  )
}

function SectionHeading({ id, title }: { id: string; title: string }) {
  return <h2 className="mb-3 font-mono text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-ink-muted" id={id}>{title}</h2>
}

function SegmentedControl({ mode, onChange }: { mode: 'spend' | 'count'; onChange: (mode: 'spend' | 'count') => void }) {
  const { t } = useTranslation()
  return <div aria-label={t('analytics.storeMode.label')} className="flex rounded-md border border-line bg-canvas p-0.5" role="group">{(['spend', 'count'] as const).map((value) => <button aria-pressed={mode === value} className={`rounded px-2.5 py-1.5 text-xs font-semibold ${mode === value ? 'bg-surface-raised text-ink shadow-sm' : 'text-ink-muted hover:text-ink'}`} key={value} onClick={() => onChange(value)} type="button">{t(`analytics.storeMode.${value}`)}</button>)}</div>
}

function CoverageItem({ label, value, help, to }: { label: string; value: string; help?: string; to?: string }) {
  const content = <><dt className="text-xs text-ink-muted">{label}</dt><dd className="mt-1 font-semibold text-ink">{value}</dd>{help && <p className="mt-1 text-xs leading-5 text-ink-muted" title={help}>{help}</p>}</>
  return to ? <Link className="rounded-lg bg-canvas p-4 hover:ring-1 hover:ring-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" to={to}>{content}</Link> : <div className="rounded-lg bg-canvas p-4">{content}</div>
}

function FatalError({ onRetry, isFetching }: { onRetry: () => void; isFetching: boolean }) {
  const { t } = useTranslation()
  return <div className="rounded-xl border border-red-500/30 bg-surface px-6 py-14 text-center" role="alert"><AlertCircle aria-hidden="true" className="mx-auto size-6 text-red-600 dark:text-red-400" /><h2 className="mt-3 text-lg font-semibold text-ink">{t('analytics.loadError')}</h2><p className="mt-2 text-sm text-ink-muted">{t('analytics.loadErrorDescription')}</p><button className="mt-5 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar disabled:opacity-60" disabled={isFetching} onClick={onRetry} type="button">{isFetching ? t('analytics.retrying') : t('common.retry')}</button></div>
}
