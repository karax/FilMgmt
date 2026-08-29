import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { makeSpool } from '../test/spoolFixture'
import type { Spool } from '../types/spool'
import { DashboardPage } from './DashboardPage'

function responseWith(data: Spool[], ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 503,
    json: vi.fn().mockResolvedValue(data),
  } as unknown as Response
}

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )

  return { user: userEvent.setup() }
}

function statCard(title: string): HTMLElement {
  const heading = screen.getByRole('heading', { level: 3, name: title })
  const card = heading.closest('article')
  if (!card) throw new Error(`Stat card not found: ${title}`)
  return card
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows skeletons while the spool query is loading', () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => undefined))

    renderDashboard()

    expect(
      screen.getByRole('status', { name: 'Loading inventory dashboard' }),
    ).toBeVisible()
    expect(screen.queryByText('No filament spools yet.')).not.toBeInTheDocument()
  })

  it('shows zero totals and the empty state for an empty inventory', async () => {
    vi.mocked(fetch).mockResolvedValue(responseWith([]))

    renderDashboard()

    expect(await screen.findByText('No filament spools yet.')).toBeVisible()
    expect(within(statCard('Total Spools')).getByText('0')).toBeVisible()
    expect(within(statCard('Available Filament')).getByText('0 g')).toBeVisible()
    expect(within(statCard('Low Spools')).getByText('0')).toBeVisible()
    expect(within(statCard('Empty Spools')).getByText('0')).toBeVisible()
    expect(within(statCard('Needs Drying')).getByText('0')).toBeVisible()
  })

  it('renders summary and material totals from returned spools', async () => {
    const petg = {
      ...makeSpool().material,
      id: 2,
      name: 'PETG',
      category: 'PETG',
    }
    vi.mocked(fetch).mockResolvedValue(
      responseWith([
        makeSpool({ id: 1, current_filament_weight_g: 800 }),
        makeSpool({
          id: 2,
          current_filament_weight_g: 150,
          remaining_percent: 15,
          status: 'LOW',
        }),
        makeSpool({
          id: 3,
          material_id: 2,
          material: petg,
          current_filament_weight_g: 0,
          remaining_percent: 0,
          status: 'EMPTY',
          needs_drying: true,
        }),
      ]),
    )

    renderDashboard()

    expect(await screen.findByRole('heading', { name: 'Materials' })).toBeVisible()
    expect(within(statCard('Total Spools')).getByText('3')).toBeVisible()
    expect(within(statCard('Available Filament')).getByText('950 g')).toBeVisible()
    expect(within(statCard('Low Spools')).getByText('1')).toBeVisible()
    expect(within(statCard('Empty Spools')).getByText('1')).toBeVisible()
    expect(within(statCard('Needs Drying')).getByText('1')).toBeVisible()

    const materials = screen.getByRole('heading', { name: 'Materials' }).closest('section')
    if (!materials) throw new Error('Materials section not found')
    expect(within(materials).getAllByText('PLA')[0]).toBeVisible()
    expect(within(materials).getByText('2 spools')).toBeVisible()
    expect(within(materials).getByText('950 g')).toBeVisible()
    expect(within(materials).getAllByText('PETG')[0]).toBeVisible()
    expect(within(materials).getByText('1 spool')).toBeVisible()
    expect(within(materials).getByText('0 g')).toBeVisible()
  })

  it('orders empty spools ahead of low spools in Needs Attention', async () => {
    vi.mocked(fetch).mockResolvedValue(
      responseWith([
        makeSpool({ id: 1, code: 'FIL-LOW', status: 'LOW', remaining_percent: 10 }),
        makeSpool({ id: 2, code: 'FIL-EMPTY', status: 'EMPTY', remaining_percent: 0 }),
      ]),
    )

    renderDashboard()

    const sectionHeading = await screen.findByRole('heading', {
      name: 'Needs Attention',
    })
    const section = sectionHeading.closest('section')
    if (!section) throw new Error('Needs Attention section not found')
    const spoolHeadings = within(section).getAllByRole('heading', { level: 3 })
    expect(spoolHeadings.map((heading) => heading.textContent)).toEqual([
      'FIL-EMPTY',
      'FIL-LOW',
    ])
  })

  it('shows a clear API error and Retry control', async () => {
    vi.mocked(fetch).mockResolvedValue(responseWith([], false))

    renderDashboard()

    expect(await screen.findByText('Unable to load inventory.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeVisible()
  })

  it('refetches the spool query when Retry is selected', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(responseWith([], false))
      .mockResolvedValueOnce(responseWith([]))
    const { user } = renderDashboard()

    await user.click(await screen.findByRole('button', { name: 'Retry' }))

    expect(await screen.findByText('No filament spools yet.')).toBeVisible()
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
  })
})
