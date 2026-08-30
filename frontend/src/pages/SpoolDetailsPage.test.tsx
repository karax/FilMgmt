import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { makeSpool } from '../test/spoolFixture'
import type { Spool } from '../types/spool'
import { SpoolDetailsPage } from './SpoolDetailsPage'

function response(data: Spool | null, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(data) } as unknown as Response
}

function renderPage(path = '/spools/FIL-0042') {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><Routes><Route path="/spools/:code" element={<SpoolDetailsPage />} /><Route path="/inventory" element={<p>Inventory destination</p>} /></Routes></MemoryRouter></QueryClientProvider>)
}

describe('SpoolDetailsPage', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn()))
  afterEach(() => vi.unstubAllGlobals())

  it('shows a loading skeleton', () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => undefined))
    renderPage()
    expect(screen.getByRole('status', { name: 'Loading spool details' })).toBeVisible()
  })

  it('renders full spool details and optional product information', async () => {
    vi.mocked(fetch).mockResolvedValue(response(makeSpool({ code: 'FIL-0042', product_name: 'PLA+ HS', current_filament_weight_g: '742', remaining_percent: 74.2, purchase_price: '21.99', purchase_date: '2026-08-12T12:00:00Z', nozzle_temp_min: 210, nozzle_temp_max: 230, bed_temp_min: 50, bed_temp_max: 60, needs_drying: true, location: { id: 2, name: 'Rack A / Slot 3', description: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' } })))
    renderPage()
    for (const text of ['FIL-0042', 'eSUN', 'PLA', 'PLA+ HS', 'Black', '742 g', '74.2%', 'Rack A / Slot 3', '€21.99', '12 Aug 2026', '210–230 °C', '50–60 °C', 'Needs drying']) expect((await screen.findAllByText(text))[0]).toBeVisible()
  })

  it('handles nullable fields without breaking the layout', async () => {
    vi.mocked(fetch).mockResolvedValue(response(makeSpool({ location: null, color_hex: null, purchase_price: null, purchase_date: null, nozzle_temp_min: null, nozzle_temp_max: null })))
    renderPage()
    expect(await screen.findByText('Unassigned')).toBeVisible()
    expect(screen.getAllByText('Not configured')[0]).toBeVisible()
  })

  it('shows a specific 404 state with a back link', async () => {
    vi.mocked(fetch).mockResolvedValue(response(null, 404))
    renderPage()
    expect(await screen.findByText('Spool not found.')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Back to Inventory' })).toHaveAttribute('href', '/inventory')
  })

  it('shows an error state and retries server failures', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(null, 500)).mockResolvedValueOnce(response(makeSpool()))
    renderPage()
    expect(await screen.findByText('Unable to load spool.')).toBeVisible()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('heading', { name: 'FIL-0001' })).toBeVisible()
  })

  it('identifies archived spools as historical records', async () => {
    vi.mocked(fetch).mockResolvedValue(response(makeSpool({ status: 'ARCHIVED', archived_at: '2026-08-20T00:00:00Z' })))
    renderPage()
    expect((await screen.findAllByText('ARCHIVED'))[0]).toBeVisible()
    expect(screen.getByText('This archived spool is retained as a historical record.')).toBeVisible()
  })
})
