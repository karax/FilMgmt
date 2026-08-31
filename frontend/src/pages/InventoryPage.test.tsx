import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { makeSpool } from '../test/spoolFixture'
import type { Spool } from '../types/spool'
import {
  INVENTORY_VIEW_STORAGE_KEY,
  InventoryPage,
} from './InventoryPage'

function responseWith(data: Spool[], ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 503,
    json: vi.fn().mockResolvedValue(data),
  } as unknown as Response
}

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
}

function renderInventory(queryClient = createTestQueryClient()) {
  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter><InventoryPage /></MemoryRouter>
    </QueryClientProvider>,
  )

  return { ...rendered, queryClient, user: userEvent.setup() }
}

describe('InventoryPage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows grid skeletons without rendering an empty state while loading', () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => undefined))

    renderInventory()

    expect(screen.getByRole('status', { name: 'Loading inventory' })).toBeVisible()
    expect(screen.queryByText('Your filament inventory is empty.')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Grid view' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('shows an API error and retries the shared spool query', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(responseWith([], false))
      .mockResolvedValueOnce(responseWith([]))
    const { user } = renderInventory()

    expect(await screen.findByText('Unable to load inventory.')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Retry' }))

    expect(await screen.findByText('Your filament inventory is empty.')).toBeVisible()
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
  })

  it('shows the empty state and zero count', async () => {
    vi.mocked(fetch).mockResolvedValue(responseWith([]))

    renderInventory()

    expect(await screen.findByText('Your filament inventory is empty.')).toBeVisible()
    expect(
      screen.getByText('Add your first spool to start tracking filament.'),
    ).toBeVisible()
    expect(screen.getByText('0 spools')).toBeVisible()
  })

  it('renders all essential spool information in grid view', async () => {
    const location = {
      id: 1,
      name: 'Rack A / Slot 3',
      description: null,
      created_at: '2026-08-01T12:00:00Z',
      updated_at: '2026-08-01T12:00:00Z',
    }
    vi.mocked(fetch).mockResolvedValue(
      responseWith([
        makeSpool({
          code: 'FIL-0001',
          current_filament_weight_g: '800.000',
          remaining_percent: 80,
          location_id: 1,
          location,
        }),
      ]),
    )

    renderInventory()

    const cardHeading = await screen.findByRole('heading', { name: 'FIL-0001' })
    const card = cardHeading.closest('article')
    if (!card) throw new Error('Spool card not found')
    expect(screen.getByText('1 spool')).toBeVisible()
    for (const text of ['eSUN', 'PLA', 'Black', '800 g', '80.0%', 'Open']) {
      expect(within(card).getByText(text)).toBeVisible()
    }
    expect(within(card).getByText('Rack A / Slot 3')).toBeVisible()
    expect(within(card).getByLabelText('Color: Black')).toBeVisible()
    expect(screen.getByRole('link', { name: 'View spool FIL-0001' })).toHaveAttribute(
      'href',
      '/spools/FIL-0001',
    )
  })

  it('handles missing color and location without breaking the grid', async () => {
    vi.mocked(fetch).mockResolvedValue(
      responseWith([makeSpool({ color_hex: null, location: null })]),
    )

    renderInventory()

    expect(await screen.findByText('Unassigned')).toBeVisible()
    expect(screen.getByLabelText('Color: Black')).toBeVisible()
    expect(screen.getByText('Black')).toBeVisible()
  })

  it('keeps LOW and EMPTY status text visible', async () => {
    vi.mocked(fetch).mockResolvedValue(
      responseWith([
        makeSpool({ id: 1, code: 'FIL-LOW', status: 'LOW' }),
        makeSpool({ id: 2, code: 'FIL-EMPTY', status: 'EMPTY' }),
      ]),
    )

    renderInventory()

    expect(await screen.findByText('Low')).toBeVisible()
    expect(screen.getByText('Empty')).toBeVisible()
  })

  it('renders a semantic table with essential columns', async () => {
    vi.mocked(fetch).mockResolvedValue(
      responseWith([makeSpool({ color_hex: null, location: null })]),
    )
    const { user } = renderInventory()

    await screen.findByRole('heading', { name: 'FIL-0001' })
    await user.click(screen.getByRole('button', { name: 'Table view' }))

    const table = screen.getByRole('table', { name: 'Spool inventory' })
    expect(table).toBeVisible()
    for (const column of [
      'Spool',
      'Manufacturer',
      'Material',
      'Color',
      'Remaining',
      'Weight',
      'Status',
      'Location',
    ]) {
      expect(within(table).getByRole('columnheader', { name: column })).toBeInTheDocument()
    }
    expect(within(table).getByText('FIL-0001')).toBeVisible()
    expect(within(table).getByText('80.0%')).toBeVisible()
    expect(within(table).getByText('—')).toBeVisible()
    expect(within(table).getByRole('link', { name: 'FIL-0001' })).toHaveAttribute(
      'href',
      '/spools/FIL-0001',
    )
  })

  it('switches grid to table and back without fetching again', async () => {
    vi.mocked(fetch).mockResolvedValue(responseWith([makeSpool()]))
    const { user } = renderInventory()

    await screen.findByRole('heading', { name: 'FIL-0001' })
    await user.click(screen.getByRole('button', { name: 'Table view' }))
    expect(screen.getByRole('table', { name: 'Spool inventory' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Grid view' }))

    expect(screen.getByRole('list', { name: 'Spools in grid view' })).toBeVisible()
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('persists table view and restores it after remounting', async () => {
    vi.mocked(fetch).mockResolvedValue(responseWith([makeSpool()]))
    const queryClient = createTestQueryClient()
    const firstRender = renderInventory(queryClient)

    await screen.findByRole('heading', { name: 'FIL-0001' })
    await firstRender.user.click(screen.getByRole('button', { name: 'Table view' }))
    expect(window.localStorage.getItem(INVENTORY_VIEW_STORAGE_KEY)).toBe('table')
    firstRender.unmount()

    renderInventory(queryClient)

    expect(screen.getByRole('button', { name: 'Table view' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('table', { name: 'Spool inventory' })).toBeVisible()
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})
