import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import { makeSpool } from '../test/spoolFixture'
import type { Spool } from '../types/spool'
import { SpoolDetailsPage } from './SpoolDetailsPage'

function response(data: unknown, status = 200): Response {
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
    vi.mocked(fetch).mockResolvedValue(response(makeSpool({ code: 'FIL-0042', product_name: 'PLA+ HS', current_filament_weight_g: '742', remaining_percent: 74.2, purchase_price: '21.99', store_name: 'Filament World', purchase_date: '2026-08-12T12:00:00Z', nozzle_temp_min: 210, nozzle_temp_max: 230, bed_temp_min: 50, bed_temp_max: 60, needs_drying: true })))
    renderPage()
    for (const text of ['FIL-0042', 'eSUN', 'PLA', 'PLA+ HS', 'Black', '742 g', '74.2%', 'Filament World', '€21.99', 'Aug 12, 2026', '210–230 °C', '50–60 °C', 'Needs drying']) expect((await screen.findAllByText(text))[0]).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Storage' })).not.toBeInTheDocument()
  })

  it('places Print Settings immediately before Basic Information', async () => {
    vi.mocked(fetch).mockResolvedValue(response(makeSpool()))
    renderPage()

    const printingSettings = await screen.findByRole('heading', { name: 'Print Settings' })
    const basicInformation = screen.getByRole('heading', { name: 'Basic Information' })
    expect(printingSettings.closest('section')?.nextElementSibling).toContainElement(
      basicInformation,
    )
  })

  it('uses a custom spool name as the detail title while retaining the code', async () => {
    vi.mocked(fetch).mockResolvedValue(response(makeSpool({ code: 'FIL-0042', display_name: 'PLA Preto Principal' })))
    renderPage()
    expect(await screen.findByRole('heading', { name: 'PLA Preto Principal' })).toBeVisible()
    expect(screen.getAllByText('FIL-0042')[0]).toBeVisible()
  })

  it('shows the QR section with the canonical code, display name, and payload', async () => {
    vi.mocked(fetch).mockResolvedValue(response(makeSpool({ code: 'FIL-0007', display_name: 'Bambu Lab Preto' })))
    renderPage('/spools/FIL-0007')

    const title = await screen.findByRole('heading', { name: 'QR Code' })
    const section = title.closest('section')
    expect(section).not.toBeNull()
    expect(within(section as HTMLElement).getByText('Bambu Lab Preto')).toBeVisible()
    expect(within(section as HTMLElement).getByText('FIL-0007')).toBeVisible()
    expect(within(section as HTMLElement).getByRole('img', { name: 'QR code for spool FIL-0007' }))
      .toHaveAttribute('data-qr-payload', 'fcc:spool:FIL-0007')
    expect(within(section as HTMLElement).getByRole('button', { name: 'Download QR' })).toBeEnabled()
  })

  it('keeps the QR and code visible when display_name is null', async () => {
    vi.mocked(fetch).mockResolvedValue(response(makeSpool({ code: 'FIL-0007', display_name: null })))
    renderPage('/spools/FIL-0007')

    const section = (await screen.findByRole('heading', { name: 'QR Code' })).closest('section')
    expect(section).not.toBeNull()
    expect(within(section as HTMLElement).getByText('FIL-0007')).toBeVisible()
    expect(within(section as HTMLElement).getByRole('img', { name: 'QR code for spool FIL-0007' }))
      .toHaveAttribute('data-qr-payload', 'fcc:spool:FIL-0007')
  })

  it('downloads the QR using the predictable SVG filename', async () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:spool-qr')
    const revokeObjectURL = vi.fn()
    class MockURL extends URL {}
    Object.assign(MockURL, { createObjectURL, revokeObjectURL })
    vi.stubGlobal('URL', MockURL)
    let downloadedFilename = ''
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function captureDownload(this: HTMLAnchorElement) {
      downloadedFilename = this.download
    })
    vi.mocked(fetch).mockResolvedValue(response(makeSpool({ code: 'FIL-0007' })))
    renderPage('/spools/FIL-0007')

    await userEvent.setup().click(await screen.findByRole('button', { name: 'Download QR' }))

    expect(downloadedFilename).toBe('FIL-0007-qr.svg')
    expect(createObjectURL).toHaveBeenCalledWith(expect.objectContaining({ type: 'image/svg+xml;charset=utf-8' }))
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:spool-qr')
  })

  it('renders the QR copy in pt-BR', async () => {
    await i18n.changeLanguage('pt-BR')
    vi.mocked(fetch).mockResolvedValue(response(makeSpool({ code: 'FIL-0007' })))
    renderPage('/spools/FIL-0007')

    expect(await screen.findByText('Identifique este spool usando o QR Code.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Baixar QR' })).toBeEnabled()
    expect(screen.getByRole('img', { name: 'QR Code do spool FIL-0007' })).toBeVisible()
    expect(screen.getByText('Restante')).toBeVisible()
    expect(screen.getByLabelText('Cor: Black')).toBeVisible()
  })

  it('handles nullable fields without breaking the layout', async () => {
    vi.mocked(fetch).mockResolvedValue(response(makeSpool({ store_name: null, color_hex: null, purchase_price: null, purchase_date: null, nozzle_temp_min: null, nozzle_temp_max: null })))
    renderPage()
    expect((await screen.findAllByText('—')).length).toBeGreaterThan(0)
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
    expect((await screen.findAllByText('Archived'))[0]).toBeVisible()
    expect(screen.getByText('This archived spool is retained as a historical record.')).toBeVisible()
  })

  it('archives an active spool only after confirmation', async () => {
    const spool = makeSpool({ code: 'FIL-0042' })
    vi.mocked(fetch).mockResolvedValueOnce(response(spool)).mockResolvedValueOnce(response({ ...spool, status: 'ARCHIVED', archived_at: '2026-08-20T00:00:00Z' }))
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Archive Spool' }))
    expect(screen.getByRole('dialog', { name: 'Archive FIL-0042?' })).toBeVisible()
    await user.click(within(screen.getByRole('dialog', { name: 'Archive FIL-0042?' })).getByRole('button', { name: 'Archive Spool' }))
    expect(fetch).toHaveBeenCalledWith('/api/spools/FIL-0042/archive', expect.objectContaining({ method: 'POST' }))
  })

  it('requires the exact code before permanently deleting an archived spool', async () => {
    vi.mocked(fetch).mockResolvedValue(response(makeSpool({ code: 'FIL-0042', status: 'ARCHIVED', archived_at: '2026-08-20T00:00:00Z' })))
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Delete Spool' }))
    const deleteButton = screen.getByRole('button', { name: 'Delete Permanently' })
    expect(deleteButton).toBeDisabled()
    await user.type(screen.getByLabelText('Type FIL-0042 to confirm'), 'FIL-0042')
    expect(deleteButton).toBeEnabled()
  })

  it('previews a manual physical calibration without mutating until explicit confirmation', async () => {
    const spool = makeSpool({ code: 'FIL-0042', current_filament_weight_g: '684.200' })
    const preview = { measured_total_g: '631.000', tare_g: '224.000', calculated_filament_g: '407.000', current_remaining_g: '684.200', adjustment_g: '-277.200', tare_source: 'MEASURED', tare_confidence: 'HIGH', tare_profile_id: null, is_estimated: false, unreconciled_prints: [] }
    const event = { id: 1, spool_id: spool.id, event_type: 'PHYSICAL_CALIBRATION', measured_total_g: '631.000', tare_g_used: '224.000', calculated_filament_g: '407.000', previous_remaining_g: '684.200', adjustment_g: '-277.200', new_remaining_g: '407.000', tare_source_used: 'MEASURED', tare_confidence_used: 'HIGH', tare_profile_id: null, tare_profile_name: null, note: null, reversed_calibration_id: null, reversed_at: null, effective_at: '2026-10-06T10:24:00Z', created_at: '2026-10-06T10:24:00Z' }
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.endsWith('/tare-profiles')) return response([])
      if (url.endsWith('/calibrations/preview')) return response(preview)
      if (url.endsWith('/calibrations') && init?.method === 'POST') return response(event, 201)
      if (url.endsWith('/calibrations')) return response([])
      return response(spool)
    })
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Calibrate weight' }))
    await user.click(screen.getByLabelText('Enter an empty spool weight'))
    await user.type(screen.getByRole('spinbutton', { name: /Physical weight/ }), '631.000')
    await user.type(screen.getByLabelText('Empty spool weight'), '224.000')
    await user.selectOptions(screen.getByLabelText('Tare source'), 'MEASURED')
    await user.selectOptions(screen.getByLabelText('Confidence'), 'HIGH')
    await user.click(screen.getByRole('button', { name: 'Review calibration' }))
    expect(await screen.findByText('-277.2 g')).toBeVisible()
    expect(vi.mocked(fetch).mock.calls.filter(([url, init]) => String(url).endsWith('/calibrations') && init?.method === 'POST')).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: 'Confirm calibration' }))
    expect(await screen.findByText('Physical calibration saved.')).toBeVisible()
    expect(vi.mocked(fetch).mock.calls.some(([url, init]) => String(url).endsWith('/calibrations') && init?.method === 'POST')).toBe(true)
  })

  it('makes the unknown-tare limitation explicit', async () => {
    vi.mocked(fetch).mockImplementation(async (input) => String(input).endsWith('/tare-profiles') || String(input).endsWith('/calibrations') ? response([]) : response(makeSpool()))
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Calibrate weight' }))
    await user.type(screen.getByRole('spinbutton', { name: /Physical weight/ }), '637')
    await user.click(screen.getByLabelText('I do not know the empty spool weight'))
    expect(screen.getByText(/Exact filament remaining cannot be calculated/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Review calibration' })).toBeDisabled()
  })
})
