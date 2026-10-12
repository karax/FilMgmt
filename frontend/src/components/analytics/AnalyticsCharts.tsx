import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartOptions,
} from 'chart.js'
import { Bar, Doughnut, Line } from 'react-chartjs-2'
import { Link } from 'react-router-dom'

import { asNumber, formatCurrency, formatDuration, formatGrams, formatPeriodLabel } from '../../lib/analytics'
import type {
  AnalyticsBucket,
  DimensionConsumption,
  InventoryByMaterial,
  PrintActivity,
  PurchaseSpendSeries,
  SpoolConsumptionRank,
  StoreSpend,
  StoreSpoolCount,
} from '../../types/analytics'

ChartJS.register(ArcElement, BarElement, CategoryScale, Legend, LinearScale, LineElement, PointElement, Tooltip)

const accent = '#119c94'
const palette = ['#119c94', '#4c7fd1', '#d59a36', '#d65f5f']
const muted = '#718096'
const grid = 'rgba(113, 128, 150, 0.18)'

function lineOptions(locale: string, formatter: (value: number) => string): ChartOptions<'line'> {
  return {
    animation: false,
    maintainAspectRatio: false,
    responsive: true,
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (context) => `${context.dataset.label ?? ''}: ${formatter(context.parsed.y ?? 0)}` } },
    },
    scales: {
      x: { border: { display: false }, grid: { display: false }, ticks: { autoSkip: true, color: muted, font: { size: 11 }, maxRotation: 0 } },
      y: { beginAtZero: true, border: { display: false }, grid: { color: grid }, ticks: { color: muted, callback: (value) => formatter(Number(value)), font: { size: 11 } } },
    },
    locale,
  }
}

function barOptions(locale: string, formatter: (value: number) => string): ChartOptions<'bar'> {
  return {
    animation: false,
    indexAxis: 'y',
    maintainAspectRatio: false,
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (context) => formatter(context.parsed.x ?? 0) } },
    },
    scales: {
      x: { beginAtZero: true, border: { display: false }, display: false, grid: { color: grid } },
      y: { border: { display: false }, grid: { display: false }, ticks: { autoSkip: false, color: muted, font: { size: 11 } } },
    },
    locale,
  }
}

function ChartFrame({ children }: { label: string; children: React.ReactNode }) {
  return <div className="h-72 w-full">{children}</div>
}

export function ConsumptionLineChart({ points, bucket, locale, label }: { points: Array<{ period: string; consumption_g: string }>; bucket: AnalyticsBucket; locale: string; label: string }) {
  return (
    <ChartFrame label={label}>
      <Line
        aria-label={label}
        data={{ labels: points.map((point) => formatPeriodLabel(point.period, bucket, locale)), datasets: [{ label, data: points.map((point) => asNumber(point.consumption_g)), borderColor: accent, backgroundColor: accent, borderWidth: 2.25, pointRadius: 0, pointHoverRadius: 4, tension: 0.28 }] }}
        options={lineOptions(locale, (value) => formatGrams(value, locale))}
      />
    </ChartFrame>
  )
}

function RankedBarChart({ labels, values, locale, valueFormatter, ariaLabel }: { labels: string[]; values: number[]; locale: string; valueFormatter: (value: number) => string; ariaLabel: string }) {
  return (
    <ChartFrame label={ariaLabel}>
      <Bar
        aria-label={ariaLabel}
        data={{ labels, datasets: [{ label: ariaLabel, data: values, backgroundColor: accent, borderRadius: 4, borderSkipped: false, barPercentage: 0.7 }] }}
        options={barOptions(locale, valueFormatter)}
      />
    </ChartFrame>
  )
}

export function TopSpoolsChart({ data, locale, label }: { data: SpoolConsumptionRank[]; locale: string; label: string }) {
  return (
    <>
      <RankedBarChart ariaLabel={label} labels={data.map((item) => item.code)} locale={locale} valueFormatter={(value) => formatGrams(value, locale)} values={data.map((item) => asNumber(item.consumption_g))} />
      <ol className="mt-4 space-y-2 border-t border-line pt-3">
        {data.slice(0, 5).map((item) => (
          <li className="flex min-w-0 items-center justify-between gap-3 text-xs" key={item.spool_id}>
            <Link className="min-w-0 truncate font-semibold text-ink hover:text-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" to={`/spools/${encodeURIComponent(item.code)}`}>{item.code} · {item.display_name}</Link>
            <span className="shrink-0 font-mono text-ink-muted">{formatGrams(item.consumption_g, locale)}</span>
          </li>
        ))}
      </ol>
    </>
  )
}

export function DimensionBarChart({ data, locale, label }: { data: DimensionConsumption[]; locale: string; label: string }) {
  return <><RankedBarChart ariaLabel={label} labels={data.map((item) => item.name)} locale={locale} valueFormatter={(value) => formatGrams(value, locale)} values={data.map((item) => asNumber(item.consumption_g))} /><ul className="sr-only">{data.map((item) => <li key={item.name}>{item.name}: {formatGrams(item.consumption_g, locale)}</li>)}</ul></>
}

export function InventoryBarChart({ data, locale, label }: { data: InventoryByMaterial[]; locale: string; label: string }) {
  return <><RankedBarChart ariaLabel={label} labels={data.map((item) => item.material)} locale={locale} valueFormatter={(value) => formatGrams(value, locale)} values={data.map((item) => asNumber(item.remaining_g))} /><ul className="sr-only">{data.map((item) => <li key={item.material}>{item.material}: {formatGrams(item.remaining_g, locale)}</li>)}</ul></>
}

export function StoreBarChart({ spend, count, mode, locale, label }: { spend: StoreSpend[]; count: StoreSpoolCount[]; mode: 'spend' | 'count'; locale: string; label: string }) {
  const data = mode === 'spend'
    ? spend.map((item) => ({ name: item.store, value: asNumber(item.amount) }))
    : count.map((item) => ({ name: item.store, value: item.spool_count }))
  const currencies = new Set(spend.map((item) => item.currency))
  const formatter = (value: number) => mode === 'count'
    ? new Intl.NumberFormat(locale).format(value)
    : currencies.size === 1 ? formatCurrency(value, spend[0]?.currency ?? 'EUR', locale) : new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value)
  return <><RankedBarChart ariaLabel={label} labels={data.map((item) => item.name)} locale={locale} valueFormatter={formatter} values={data.map((item) => item.value)} /><ul className="sr-only">{data.map((item) => <li key={item.name}>{item.name}: {formatter(item.value)}</li>)}</ul></>
}

export function PurchaseLineChart({ series, locale, label }: { series: PurchaseSpendSeries; locale: string; label: string }) {
  const currencies = [...new Set(series.points.map((point) => point.currency))]
  const periods = [...new Set(series.points.map((point) => point.period))]
  const datasets = currencies.map((currency, index) => ({
    label: currency,
    data: periods.map((period) => asNumber(series.points.find((point) => point.period === period && point.currency === currency)?.amount)),
    borderColor: palette[index % palette.length],
    backgroundColor: palette[index % palette.length],
    borderWidth: 2.25,
    pointRadius: 0,
    pointHoverRadius: 4,
    tension: 0.28,
  }))
  const options = lineOptions(locale, (value) => new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value))
  options.plugins = { ...options.plugins, legend: { display: currencies.length > 1, labels: { color: muted } }, tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${formatCurrency(context.parsed.y ?? 0, context.dataset.label ?? 'EUR', locale)}` } } }
  return <ChartFrame label={label}><Line aria-label={label} data={{ labels: periods.map((period) => formatPeriodLabel(period, series.bucket, locale)), datasets }} options={options} /></ChartFrame>
}

export function PrintOutcomesChart({ activity, label, labels }: { activity: PrintActivity; label: string; labels: Record<'completed' | 'failed' | 'cancelled' | 'unknown', string> }) {
  const data = [
    { name: labels.completed, value: activity.outcomes.completed },
    { name: labels.failed, value: activity.outcomes.failed },
    { name: labels.cancelled, value: activity.outcomes.cancelled },
    { name: labels.unknown, value: activity.outcomes.unknown_terminal },
  ]
  const options: ChartOptions<'doughnut'> = { animation: false, maintainAspectRatio: false, responsive: true, cutout: '62%', plugins: { legend: { display: false } } }
  return (
    <div className="grid items-center gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
      <ChartFrame label={label}><Doughnut aria-label={label} data={{ labels: data.map((item) => item.name), datasets: [{ data: data.map((item) => item.value), backgroundColor: palette, borderColor: 'transparent', spacing: 2 }] }} options={options} /></ChartFrame>
      <ul className="space-y-2 text-xs">
        {data.map((entry, index) => <li className="flex min-w-36 items-center justify-between gap-4" key={entry.name}><span className="flex items-center gap-2 text-ink-muted"><span aria-hidden="true" className="size-2 rounded-full" style={{ backgroundColor: palette[index] }} />{entry.name}</span><strong className="text-ink">{entry.value}</strong></li>)}
      </ul>
    </div>
  )
}

export function ActivityLineChart({ activity, locale, label }: { activity: PrintActivity; locale: string; label: string }) {
  const points = activity.printing_seconds_by_period
  const options = lineOptions(locale, (value) => `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(value)}h`)
  options.plugins = { ...options.plugins, tooltip: { callbacks: { label: (context) => `${label}: ${formatDuration(points[context.dataIndex]?.count ?? 0, locale)}` } } }
  return <ChartFrame label={label}><Line aria-label={label} data={{ labels: points.map((point) => formatPeriodLabel(point.period, activity.bucket, locale)), datasets: [{ label, data: points.map((point) => point.count / 3600), borderColor: accent, backgroundColor: accent, borderWidth: 2.25, pointRadius: 0, pointHoverRadius: 4, tension: 0.28 }] }} options={options} /></ChartFrame>
}
