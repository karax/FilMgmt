import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AnalyticsFilters } from '../../types/analytics'
import { AnalyticsExportDialog } from './AnalyticsExportDialog'

const filters: AnalyticsFilters = {
  range: 'custom',
  from: '2026-10-01',
  to: '2026-10-31',
  timezone: 'Europe/Lisbon',
  material: 'PETG',
  brand: 'eSUN',
  store: '3DJake',
  spoolId: 20,
}

function csvResponse(ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 503,
    headers: new Headers({ 'Content-Disposition': 'attachment; filename="confirmed-consumption-custom-2026-10-12.csv"' }),
    blob: vi.fn().mockResolvedValue(new Blob(['a,b\r\n1,2\r\n'], { type: 'text/csv' })),
    json: vi.fn().mockResolvedValue({ detail: 'unavailable' }),
  } as unknown as Response
}

function renderDialog(overrides: Partial<React.ComponentProps<typeof AnalyticsExportDialog>> = {}) {
  const props = {
    bucket: 'month' as const,
    filters,
    onClose: vi.fn(),
    onDownloaded: vi.fn(),
    ...overrides,
  }
  render(<AnalyticsExportDialog {...props} />)
  return { ...props, user: userEvent.setup() }
}

describe('AnalyticsExportDialog', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:csv') })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('shows human-readable analytics and raw dataset groups', () => {
    renderDialog()
    const dialog = screen.getByRole('dialog', { name: 'Export data' })
    expect(within(dialog).getByText('Analytics')).toBeVisible()
    expect(within(dialog).getByText('Raw data')).toBeVisible()
    expect(within(dialog).getByRole('radio', { name: 'Consumption over time' })).toBeChecked()
    expect(within(dialog).getByRole('radio', { name: 'Spool inventory' })).toBeVisible()
    expect(within(dialog).getByRole('radio', { name: 'Inventory ledger' })).toBeVisible()
    expect(within(dialog).getByRole('radio', { name: 'Physical calibrations' })).toBeVisible()
    expect(within(dialog).getByText('This dataset uses the date range and filters currently selected on Analytics.')).toBeVisible()
  })

  it('downloads an analytics dataset with current date and dimension filters using GET', async () => {
    vi.mocked(fetch).mockResolvedValue(csvResponse())
    const { user, onDownloaded } = renderDialog()
    await user.click(screen.getByRole('button', { name: 'Export CSV' }))

    await waitFor(() => expect(onDownloaded).toHaveBeenCalledWith('confirmed-consumption-custom-2026-10-12.csv'))
    expect(fetch).toHaveBeenCalledTimes(1)
    const [url, init] = vi.mocked(fetch).mock.calls[0]
    const parsed = new URL(String(url), 'http://localhost')
    expect(parsed.pathname).toBe('/api/analytics/export')
    expect(Object.fromEntries(parsed.searchParams)).toMatchObject({
      dataset: 'consumption_over_time', range: 'custom', from: '2026-10-01', to: '2026-10-31',
      timezone: 'Europe/Lisbon', material: 'PETG', brand: 'eSUN', store: '3DJake',
      spool_id: '20', bucket: 'month', scope: 'current',
    })
    expect(init?.method).toBe('GET')
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledOnce()
  })

  it('allows a raw dataset to explicitly export all data', async () => {
    vi.mocked(fetch).mockResolvedValue(csvResponse())
    const { user } = renderDialog()
    await user.click(screen.getByRole('radio', { name: 'Confirmed consumption' }))
    expect(screen.getByRole('radio', { name: /^Current Analytics filters/ })).toBeChecked()
    await user.click(screen.getByRole('radio', { name: /^All data/ }))
    await user.click(screen.getByRole('button', { name: 'Export CSV' }))

    await waitFor(() => expect(fetch).toHaveBeenCalledOnce())
    const parsed = new URL(String(vi.mocked(fetch).mock.calls[0][0]), 'http://localhost')
    expect(parsed.searchParams.get('dataset')).toBe('confirmed_consumption')
    expect(parsed.searchParams.get('scope')).toBe('all')
  })

  it('shows a pending state without issuing write requests', async () => {
    let resolveResponse: ((response: Response) => void) | undefined
    vi.mocked(fetch).mockReturnValue(new Promise((resolve) => { resolveResponse = resolve }))
    const { user } = renderDialog()
    await user.click(screen.getByRole('button', { name: 'Export CSV' }))
    expect(screen.getByRole('button', { name: 'Preparing CSV…' })).toBeDisabled()
    expect(vi.mocked(fetch).mock.calls[0][1]?.method).toBe('GET')
    resolveResponse?.(csvResponse())
    await waitFor(() => expect(screen.getByRole('button', { name: 'Export CSV' })).toBeEnabled())
  })

  it('shows a safe retryable error message', async () => {
    vi.mocked(fetch).mockResolvedValue(csvResponse(false))
    const { user } = renderDialog()
    await user.click(screen.getByRole('button', { name: 'Export CSV' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not export data. Please try again.')
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeEnabled()
  })

  it('closes with Cancel, the close button, and Escape', async () => {
    const first = renderDialog()
    await first.user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(first.onClose).toHaveBeenCalledOnce()

    const second = renderDialog()
    const dialogs = screen.getAllByRole('dialog', { name: 'Export data' })
    await second.user.click(within(dialogs.at(-1) as HTMLElement).getByRole('button', { name: 'Close' }))
    expect(second.onClose).toHaveBeenCalledOnce()

    const third = renderDialog()
    await third.user.keyboard('{Escape}')
    expect(third.onClose).toHaveBeenCalledOnce()
  })
})
