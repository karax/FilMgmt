import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AnalyticsPage } from './AnalyticsPage'

const period = { preset: 'all_time', from: null, to: '2026-10-12T23:00:00Z', timezone: 'Europe/Lisbon', date_field: 'started_at' }
const dashboard = {
  period,
  consumption: { confirmed_g: '1310.070', confirmed_kg: '1.310', estimated_costs: [{ currency: 'EUR', amount: '20.30' }], confirmed_g_with_known_cost: '1310.070', cost_coverage_percentage: '100.00' },
  printing: { actual_printing_seconds: 270321, actual_printing_hours: '75.09', jobs_with_actual_duration: 17, total_terminal_jobs: 24, duration_coverage_percentage: '70.83', completed: 17, failed: 6, cancelled: 0, unknown_terminal: 1, success_rate_percentage: '73.91' },
  inventory: { active_spool_count: 47, current_remaining_g: '40819.930', empty_spool_count: 14, archived_spool_count: 0 },
  reconciliation: { pending_print_count: 8, pending_filament_usage_count: 8 },
  highlights: {
    most_used_spool: { spool_id: 30, code: 'FIL-0030', display_name: 'Sunlu PLA Wood Walnut', brand: 'SUNLU', material: 'PLA Wood', color: 'Walnut', consumption_g: '730.079', print_count: 2 },
    most_consumed_material: { name: 'PLA Wood', consumption_g: '730.079', print_count: 2 },
    most_consumed_brand: { name: 'SUNLU', consumption_g: '741.559', print_count: 3 },
    highest_spend_stores_by_currency: [{ store: 'Filamentos Pro', currency: 'EUR', amount: '318.76', priced_spool_count: 18 }],
    most_spools_store: { store: 'Filamentos Pro', spool_count: 22 },
  },
}

const responses: Record<string, unknown> = {
  dashboard,
  'consumption-over-time': { period, bucket: 'month', points: [{ period: '2026-10', consumption_g: '1310.070' }], unbucketed_consumption_g: '0.000' },
  'top-spools': [dashboard.highlights.most_used_spool],
  'consumption-by-material': [dashboard.highlights.most_consumed_material],
  'consumption-by-brand': [dashboard.highlights.most_consumed_brand, { name: 'Unknown', consumption_g: '12.000', print_count: 1 }],
  'inventory-by-material': [{ material: 'PLA', remaining_g: '12400.000', spool_count: 14 }],
  'purchases-by-store': { period, by_spend: dashboard.highlights.highest_spend_stores_by_currency, by_spool_count: [dashboard.highlights.most_spools_store] },
  'purchase-spend-over-time': { period, bucket: 'month', points: [{ period: '2026-10', currency: 'EUR', amount: '318.76' }], unbucketed_amounts: [{ currency: 'EUR', amount: '318.76' }] },
  'print-activity': { period, bucket: 'month', outcomes: { completed: 17, failed: 6, cancelled: 0, unknown_terminal: 1, success_rate_percentage: '73.91' }, activity: { actual_printing_seconds: 270321, actual_printing_hours: '75.09', jobs_with_actual_duration: 17, total_terminal_jobs: 24, duration_coverage_percentage: '70.83' }, printing_seconds_by_period: [{ period: '2026-10', count: 270321 }], completed_prints_by_period: [{ period: '2026-10', count: 17 }] },
  'top-consuming-prints': [{ print_job_id: 42, name: 'Desk Robot Body', started_at: '2026-10-01T12:00:00Z', consumption_g: '312.400' }],
}

function endpoint(url: string): string {
  return new URL(url, 'http://localhost').pathname.split('/').at(-1) ?? ''
}

function responseWith(data: unknown, ok = true): Response {
  return { ok, status: ok ? 200 : 503, json: vi.fn().mockResolvedValue(data) } as unknown as Response
}

function mockAnalytics(overrides: Record<string, unknown | 'ERROR'> = {}) {
  vi.mocked(fetch).mockImplementation(async (input, init) => {
    const key = endpoint(String(input))
    const value = key in overrides ? overrides[key] : responses[key]
    if (value === 'ERROR') return responseWith({ detail: 'unavailable' }, false)
    if (!value) throw new Error(`Unexpected analytics endpoint: ${String(input)} (${init?.method})`)
    return responseWith(value)
  })
}

function renderAnalytics(path = '/analytics?range=all_time') {
  const router = createMemoryRouter([{ path: '/analytics', element: <AnalyticsPage /> }], { initialEntries: [path] })
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>)
  return { router, user: userEvent.setup() }
}

function card(title: string): HTMLElement {
  const heading = screen.getByRole('heading', { level: 3, name: title })
  const result = heading.closest('article, a')
  if (!result) throw new Error(`Missing card: ${title}`)
  return result as HTMLElement
}

describe('AnalyticsPage', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn()))
  afterEach(() => vi.unstubAllGlobals())

  it('shows stable dashboard skeletons while the summary is loading', () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => undefined))
    renderAnalytics()
    expect(screen.getByRole('status', { name: 'Loading analytics dashboard' })).toBeVisible()
  })

  it('opens the grouped CSV export dialog from the Analytics header', async () => {
    mockAnalytics()
    const { user } = renderAnalytics()
    await screen.findByText('1.31 kg')
    await user.click(screen.getByRole('button', { name: 'Export data' }))
    expect(screen.getByRole('dialog', { name: 'Export data' })).toBeVisible()
    expect(screen.getByRole('radio', { name: 'Consumption over time' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Spool inventory' })).toBeVisible()
  })

  it('renders canonical KPIs, highlights, every chart, coverage, and drill-down links', async () => {
    mockAnalytics()
    renderAnalytics()

    expect(await screen.findByText('1.31 kg')).toBeVisible()
    expect(within(card('Material cost')).getByText('€20.30')).toBeVisible()
    expect(within(card('Material cost')).getByText('100% data coverage')).toBeVisible()
    expect(within(card('Current inventory')).getByText('40.82 kg')).toBeVisible()
    expect(within(card('Current inventory')).getByText(/47 active spools/)).toBeVisible()
    expect(within(card('Completed prints')).getByText('17')).toBeVisible()
    expect(within(card('Success rate')).getByText('73.91%')).toBeVisible()
    expect(within(card('Pending reconciliation')).getByText('8')).toBeVisible()
    expect(within(card('Pending reconciliation')).getByText('8 filament usages')).toBeVisible()
    expect(screen.getAllByRole('link', { name: /FIL-0030/ }).every((link) => link.getAttribute('href') === '/spools/FIL-0030')).toBe(true)
    expect(screen.getByText('SUNLU')).toBeVisible()
    expect(screen.getAllByText('Filamentos Pro').length).toBeGreaterThan(0)
    expect(screen.getByText(/^Unknown:/)).toBeInTheDocument()

    for (const label of ['Confirmed consumption over time', 'Most-used physical spools', 'Consumption by material', 'Consumption by brand', 'Current inventory by material', 'Purchases by store', 'Purchase spending over time', 'Print outcomes', 'Printer activity']) {
      expect(screen.getByRole('img', { name: label })).toBeInTheDocument()
    }
    expect(screen.getByRole('heading', { name: 'Largest prints by confirmed filament' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Desk Robot Body' })).toHaveAttribute('href', '/prints/42')
    expect(screen.getByText(/75h 5m observed/)).toBeVisible()
    expect(screen.getAllByText('70.83%').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /8/ }).some((link) => link.getAttribute('href') === '/reconciliation')).toBe(true)

    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(10)
    for (const [, init] of vi.mocked(fetch).mock.calls) expect(init?.method).toBe('GET')
  })

  it('keeps preset and custom range state in the URL and sends it to every query', async () => {
    mockAnalytics()
    const { router, user } = renderAnalytics('/analytics?range=last_30_days')
    await screen.findByText('1.31 kg')

    await user.selectOptions(screen.getByRole('combobox', { name: 'Date range' }), 'custom')
    expect(router.state.location.search).toBe('?range=custom')
    expect(screen.getByText('Choose both a start and end date to load a custom range.')).toBeVisible()
    await user.type(screen.getByLabelText('From'), '2026-10-01')
    await user.type(screen.getByLabelText('To'), '2026-10-12')

    await waitFor(() => expect(router.state.location.search).toContain('from=2026-10-01'))
    await waitFor(() => expect(router.state.location.search).toContain('to=2026-10-12'))
    await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('range=custom') && String(url).includes('from=2026-10-01') && String(url).includes('to=2026-10-12'))).toBe(true))
  })

  it('switches purchases-by-store between spend and spool-count rankings', async () => {
    mockAnalytics()
    const { user } = renderAnalytics()
    await screen.findByText('1.31 kg')
    const spend = screen.getByRole('button', { name: 'Spend' })
    const count = screen.getByRole('button', { name: 'Spools' })
    expect(spend).toHaveAttribute('aria-pressed', 'true')
    await user.click(count)
    expect(count).toHaveAttribute('aria-pressed', 'true')
    expect(spend).toHaveAttribute('aria-pressed', 'false')
  })

  it('keeps the dashboard usable when one chart request fails', async () => {
    mockAnalytics({ 'consumption-by-brand': 'ERROR' })
    renderAnalytics()
    expect(await screen.findByText('1.31 kg')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Consumption by brand' })).toBeVisible()
    expect(screen.getByText('This chart is temporarily unavailable.')).toBeVisible()
    expect(screen.getByRole('img', { name: 'Confirmed consumption over time' })).toBeInTheDocument()
  })

  it('shows semantic empty states rather than empty axes', async () => {
    mockAnalytics({
      'consumption-over-time': { period, bucket: 'month', points: [], unbucketed_consumption_g: '0.000' },
      'top-spools': [],
      'consumption-by-material': [],
      'consumption-by-brand': [],
      'purchases-by-store': { period, by_spend: [], by_spool_count: [] },
      'purchase-spend-over-time': { period, bucket: 'month', points: [], unbucketed_amounts: [] },
    })
    renderAnalytics()
    await screen.findByText('1.31 kg')
    expect(screen.getAllByText('No confirmed filament consumption in this period.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('No purchases were recorded in this period.').length).toBe(2)
  })

  it('shows a retryable full-page error when the summary fails', async () => {
    mockAnalytics({ dashboard: 'ERROR' })
    renderAnalytics()
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load analytics.')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeEnabled()
  })
})
