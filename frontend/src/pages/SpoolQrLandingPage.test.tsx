import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import { makeSpool } from '../test/spoolFixture'
import type { Spool } from '../types/spool'
import { SpoolQrLandingPage } from './SpoolQrLandingPage'

function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(data),
  } as unknown as Response
}

function renderPage(path = '/qr/spool/FIL-0007') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return {
    queryClient,
    user: userEvent.setup(),
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/qr/spool/:code" element={<SpoolQrLandingPage />} />
            <Route path="/spools/:code" element={<p>Full spool destination</p>} />
            <Route path="/inventory" element={<p>Inventory destination</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  }
}

function landingSpool(overrides: Partial<Spool> = {}): Spool {
  return makeSpool({
    id: 73,
    code: 'FIL-0007',
    display_name: 'Bambu Lab Preto',
    manufacturer: {
      id: 7,
      name: 'Bambu Lab',
      website: null,
      created_at: '2026-08-01T12:00:00Z',
      updated_at: '2026-08-01T12:00:00Z',
    },
    material: {
      ...makeSpool().material,
      id: 3,
      name: 'PLA',
    },
    color_name: 'Preto',
    color_hex: '#111111',
    current_filament_weight_g: '742',
    remaining_percent: 74.2,
    status: 'OPEN',
    location: { id: 2, name: 'Rack A' },
    ...overrides,
  })
}

describe('SpoolQrLandingPage', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en')
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads the spool identified by the route code rather than its database id', async () => {
    vi.mocked(fetch).mockResolvedValue(response(landingSpool()))

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Bambu Lab Preto' })).toBeVisible()
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch).toHaveBeenCalledWith(
      '/api/spools/FIL-0007',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(fetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/73'),
      expect.anything(),
    )
  })

  it('shows a stable loading state without flashing not found', () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => undefined))

    renderPage()

    expect(screen.getByRole('status', { name: 'Loading spool quick view' })).toBeVisible()
    expect(screen.queryByText('Spool not found.')).not.toBeInTheDocument()
  })

  it('rejects an invalid route code without requesting the API', () => {
    renderPage('/qr/spool/INVALID')

    expect(screen.getByRole('heading', { name: 'Invalid QR Code or spool code.' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Back to Inventory' })).toHaveAttribute(
      'href',
      '/inventory',
    )
    expect(fetch).not.toHaveBeenCalled()
  })

  it('shows the specific not-found state for a valid missing spool', async () => {
    vi.mocked(fetch).mockResolvedValue(response({ detail: 'Spool not found.' }, 404))

    renderPage('/qr/spool/FIL-9999')

    expect(await screen.findByRole('heading', { name: 'Spool not found.' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to Inventory' })).toHaveAttribute(
      'href',
      '/inventory',
    )
  })

  it('distinguishes a network error and retries the same code', async () => {
    vi.mocked(fetch)
      .mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce(response(landingSpool()))
    const { user } = renderPage()

    expect(await screen.findByRole('heading', { name: 'Unable to load this spool.' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { name: 'Bambu Lab Preto' })).toBeVisible()
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    for (const [path] of vi.mocked(fetch).mock.calls) {
      expect(path).toBe('/api/spools/FIL-0007')
    }
  })

  it('presents the quick physical identification fields and existing progress component', async () => {
    vi.mocked(fetch).mockResolvedValue(response(landingSpool()))

    renderPage()

    const page = (await screen.findByRole('heading', { name: 'Bambu Lab Preto' })).closest('article')
    if (!page) throw new Error('QR landing page not found')
    for (const text of [
      'FIL-0007',
      'Bambu Lab',
      'PLA',
      'Preto',
      '742 g',
      '74.2%',
      'Rack A',
      'Open',
    ]) {
      expect(within(page).getByText(text)).toBeVisible()
    }
    expect(within(page).getByRole('progressbar', { name: 'FIL-0007 remaining filament' }))
      .toHaveAttribute('aria-valuenow', '74.2')
    expect(within(page).getByLabelText('Color: Preto')).toBeVisible()
  })

  it('shows LOW and drying warnings without inventing a client threshold', async () => {
    vi.mocked(fetch).mockResolvedValue(response(landingSpool({
      status: 'LOW',
      needs_drying: true,
      remaining_percent: 42,
    })))

    renderPage()

    expect(await screen.findByText('Low filament')).toBeVisible()
    expect(screen.getByText('Needs drying')).toBeVisible()
    expect(screen.getByText('Low')).toBeVisible()
  })

  it.each([
    ['EMPTY' as const, 'Empty'],
    ['IN_USE' as const, 'In use'],
  ])('reflects the backend %s status', async (status, label) => {
    vi.mocked(fetch).mockResolvedValue(response(landingSpool({ status })))

    renderPage()

    expect(await screen.findByText(label)).toBeVisible()
  })

  it('continues to represent an archived spool returned by the detail endpoint', async () => {
    vi.mocked(fetch).mockResolvedValue(response(landingSpool({
      status: 'ARCHIVED',
      archived_at: '2026-08-20T00:00:00Z',
    })))

    renderPage()

    expect(await screen.findByText('Archived')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Bambu Lab Preto' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'View full details' })).toHaveAttribute(
      'href',
      '/spools/FIL-0007',
    )
  })

  it('uses the code as the title when display_name is null', async () => {
    vi.mocked(fetch).mockResolvedValue(response(landingSpool({ display_name: null })))

    renderPage()

    expect(await screen.findByRole('heading', { name: 'FIL-0007' })).toBeVisible()
  })

  it('uses safe fallbacks for missing location, weight, and percentage', async () => {
    const spool = landingSpool({ location: null })
    Object.assign(spool, {
      current_filament_weight_g: undefined,
      remaining_percent: undefined,
    })
    vi.mocked(fetch).mockResolvedValue(response(spool))

    renderPage()

    await screen.findByRole('heading', { name: 'Bambu Lab Preto' })
    expect(screen.getAllByText('—')).toHaveLength(3)
    expect(screen.queryByText(/NaN|undefined/)).not.toBeInTheDocument()
  })

  it('navigates to full details using the public code', async () => {
    vi.mocked(fetch).mockResolvedValue(response(landingSpool()))
    const { user } = renderPage()

    const link = await screen.findByRole('link', { name: 'View full details' })
    expect(link).toHaveAttribute('href', '/spools/FIL-0007')
    await user.click(link)
    expect(screen.getByText('Full spool destination')).toBeVisible()
  })

  it('uses a centered mobile-first summary without a horizontal table', async () => {
    vi.mocked(fetch).mockResolvedValue(response(landingSpool()))

    renderPage()

    const page = (await screen.findByRole('heading', { name: 'Bambu Lab Preto' })).closest('article')
    expect(page).toHaveClass('w-full', 'max-w-2xl')
    expect(within(page as HTMLElement).queryByRole('table')).not.toBeInTheDocument()
    expect(page?.querySelector('[data-layout="qr-summary-grid"]')).toBeVisible()
  })

  it('renders the landing actions and labels in pt-BR', async () => {
    await i18n.changeLanguage('pt-BR')
    vi.mocked(fetch).mockResolvedValue(response(landingSpool({ needs_drying: true })))

    renderPage()

    expect(await screen.findByText('Peso atual')).toBeVisible()
    for (const text of [
      'restante',
      'Localização',
      'Material',
      'Fabricante',
      'Precisa de secagem',
    ]) {
      expect(screen.getByText(text)).toBeVisible()
    }
    expect(screen.getByRole('link', { name: 'Ver detalhes completos' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Voltar ao Inventário' })).toBeVisible()
  })

  it('renders the landing actions and labels in English', async () => {
    vi.mocked(fetch).mockResolvedValue(response(landingSpool()))

    renderPage()

    expect(await screen.findByText('Current weight')).toBeVisible()
    for (const text of ['remaining', 'Location', 'Material', 'Manufacturer']) {
      expect(screen.getByText(text)).toBeVisible()
    }
    expect(screen.getByRole('link', { name: 'View full details' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Back to Inventory' })).toBeVisible()
  })
})
