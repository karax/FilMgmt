import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import type { ReconciliationQueue } from '../types/reconciliation'
import { ReconciliationPage } from './ReconciliationPage'

const queue: ReconciliationQueue = {
  pending_job_count: 2,
  ready_job_count: 1,
  needs_review_job_count: 1,
  estimated_pending_g: '162.708',
  recently_reconciled_jobs: [],
  available_spools: [
    { id: 42, code: 'FIL-0042', display_name: null, manufacturer_name: 'eSUN', material_name: 'PLA+', color_name: 'Black', color_hex: '#000000', current_filament_weight_g: '684.000' },
    { id: 12, code: 'FIL-0012', display_name: null, manufacturer_name: 'Bambu Lab', material_name: 'PETG', color_name: 'White', color_hex: '#FFFFFF', current_filament_weight_g: '620.000' },
    { id: 28, code: 'FIL-0028', display_name: null, manufacturer_name: 'Bambu Lab', material_name: 'PETG', color_name: 'White', color_hex: '#FFFFFF', current_filament_weight_g: '410.000' },
    { id: 77, code: 'FIL-0077', display_name: 'Manual correction', manufacturer_name: 'Polymaker', material_name: 'ABS', color_name: 'Blue', color_hex: '#0000FF', current_filament_weight_g: '900.000' },
  ],
  jobs: [
    {
      id: 101,
      name: 'Desk Robot Head',
      gcode_file: 'desk_robot_head.gcode.3mf',
      status: 'COMPLETED',
      reconciliation_status: 'PENDING',
      started_at: '2026-10-05T18:29:00Z',
      finished_at: '2026-10-05T21:47:00Z',
      duration_seconds: 11880,
      actual_time_minutes: null,
      final_progress: 100,
      selected_plate_index: 2,
      selected_plate_name: 'Robot head',
      thumbnail_url: null,
      filament_count: 1,
      estimated_filament_g: '74.200',
      filaments: [{
        id: 501,
        position: 0,
        material_type: 'PLA+',
        color: '000000FF',
        used_g: '74.200',
        progress_estimated_g: '74.200',
        used_m: '24.000',
        tray_info_idx: 'GFL99',
        ams_tray: 'AMS 0:1',
        ams_brand: 'eSUN',
        recommended_spool_id: 42,
        unambiguous: true,
        requires_manual_consumption: false,
        resolution: null,
        candidates: [{
          id: 42,
          code: 'FIL-0042',
          display_name: null,
          product_name: 'PLA+ HS',
          manufacturer_name: 'eSUN',
          material_name: 'PLA+',
          color_name: 'Black',
          color_hex: '#000000',
          current_filament_weight_g: '684.000',
          purchase_price: '18.90',
          currency: 'EUR',
          confidence: 'HIGH',
          sufficient_remaining: true,
          reasons: [{ code: 'SAME_AMS_TRAY_HISTORY', detail: 'This spool was confirmed with the same AMS tray fingerprint about 4h earlier.' }],
        }],
      }],
    },
    {
      id: 102,
      name: 'Cancelled bracket',
      gcode_file: 'bracket.gcode.3mf',
      status: 'CANCELLED',
      reconciliation_status: 'NEEDS_REVIEW',
      started_at: '2026-10-06T08:00:00Z',
      finished_at: '2026-10-06T08:20:00Z',
      duration_seconds: 1200,
      actual_time_minutes: null,
      final_progress: 37,
      selected_plate_index: 7,
      selected_plate_name: null,
      thumbnail_url: null,
      filament_count: 1,
      estimated_filament_g: '239.210',
      filaments: [{
        id: 502,
        position: 0,
        material_type: 'PETG',
        color: 'FFFFFFFF',
        used_g: '239.210',
        progress_estimated_g: '88.508',
        used_m: '75.460',
        tray_info_idx: 'GFL98',
        ams_tray: 'AMS 0:2',
        ams_brand: 'Bambu Lab',
        recommended_spool_id: null,
        unambiguous: false,
        requires_manual_consumption: true,
        resolution: null,
        candidates: [{
          id: 12,
          code: 'FIL-0012',
          display_name: null,
          product_name: 'PETG Basic',
          manufacturer_name: 'Bambu Lab',
          material_name: 'PETG',
          color_name: 'White',
          color_hex: '#FFFFFF',
          current_filament_weight_g: '620.000',
          purchase_price: '20.00',
          currency: 'EUR',
          confidence: 'AMBIGUOUS',
          sufficient_remaining: true,
          reasons: [{ code: 'MATERIAL_EXACT', detail: 'Material exactly matches the sliced filament.' }],
        }, {
          id: 28,
          code: 'FIL-0028',
          display_name: null,
          product_name: 'PETG Basic',
          manufacturer_name: 'Bambu Lab',
          material_name: 'PETG',
          color_name: 'White',
          color_hex: '#FFFFFF',
          current_filament_weight_g: '410.000',
          purchase_price: '20.00',
          currency: 'EUR',
          confidence: 'AMBIGUOUS',
          sufficient_remaining: true,
          reasons: [{ code: 'MATERIAL_EXACT', detail: 'Material exactly matches the sliced filament.' }],
        }],
      }],
    },
  ],
}

function response(data: unknown): Response {
  return { ok: true, status: 200, json: vi.fn().mockResolvedValue(data) } as unknown as Response
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter><ReconciliationPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ReconciliationPage', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(queue)))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('groups captured prints with strong memory cues and keeps identical spools selectable', async () => {
    renderPage()
    const user = userEvent.setup()
    expect(await screen.findByText('Desk Robot Head')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Reconcile prints' })).toBeVisible()
    expect(screen.getByText('Cancelled bracket')).toBeVisible()
    expect(screen.getByText('3h 18m')).toBeVisible()
    expect(screen.getByText('Plate 7')).toBeVisible()
    expect(screen.getByText(/Estimated consumption is calculated from the final progress/)).toBeVisible()

    const incompleteCard = screen.getByText('Cancelled bracket').closest('details')!
    const selector = within(incompleteCard).getByRole('combobox', { name: 'Physical inventory spool' })
    await user.click(selector)
    expect(within(incompleteCard).getByRole('option', { name: /FIL-0012/ })).toBeInTheDocument()
    expect(within(incompleteCard).getByRole('option', { name: /FIL-0028/ })).toBeInTheDocument()
    expect(within(incompleteCard).getByRole('option', { name: /FIL-0077/ })).toBeInTheDocument()
    expect(within(incompleteCard).getByRole('option', { name: 'Do not deduct' })).toBeInTheDocument()
  })

  it('filters spools dynamically by code, name, brand, material, and color', async () => {
    renderPage()
    const user = userEvent.setup()
    const incompleteCard = (await screen.findByText('Cancelled bracket')).closest('details')!
    const selector = within(incompleteCard).getByRole('combobox', { name: 'Physical inventory spool' })

    await user.click(selector)
    await user.type(selector, 'polymaker blue')

    expect(within(incompleteCard).getByRole('option', { name: /FIL-0077/ })).toBeVisible()
    expect(within(incompleteCard).queryByRole('option', { name: /FIL-0012/ })).not.toBeInTheDocument()
    await user.click(within(incompleteCard).getByRole('option', { name: /FIL-0077/ }))
    expect((selector as HTMLInputElement).value).toContain('FIL-0077')
  })

  it('confirms every selected unambiguous line in one explicit batch request', async () => {
    const confirmedQueue = { ...queue, jobs: [queue.jobs[1]], pending_job_count: 1, ready_job_count: 0 }
    vi.mocked(fetch).mockImplementation(async (_input, init) => {
      if (init?.method === 'POST') return response({ reconciled_usage_ids: [501], print_jobs: [] })
      return response(confirmedQueue)
    })
    // First GET needs the original queue; invalidation GET receives the updated queue.
    vi.mocked(fetch).mockResolvedValueOnce(response(queue))
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Select all unambiguous' }))
    await user.click(screen.getByRole('button', { name: 'Confirm 1 filament' }))

    await waitFor(() => {
      const post = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST')
      expect(post).toBeDefined()
      expect(JSON.parse(String(post?.[1]?.body))).toEqual({
        items: [{
          filament_usage_id: 501,
          action: 'DEDUCT',
          spool_id: 42,
          consumption_g: 74.2,
        }],
      })
    })
  })

  it('prefills proportional consumption and still requires a reason for an incomplete print', async () => {
    renderPage()
    const user = userEvent.setup()
    const incompleteCard = (await screen.findByText('Cancelled bracket')).closest('details')!
    const selector = within(incompleteCard).getByRole('combobox', { name: 'Physical inventory spool' })
    await user.click(selector)
    await user.type(selector, 'FIL-0012')
    await user.keyboard('{ArrowDown}{Enter}')
    expect((selector as HTMLInputElement).value).toContain('FIL-0012')
    const checkbox = within(incompleteCard).getByRole('checkbox', { name: 'Include PETG in this batch' })
    await user.click(checkbox)
    expect(screen.getByRole('button', { name: 'Confirm 1 filament' })).toBeDisabled()

    expect(within(incompleteCard).getByRole('spinbutton', { name: /Consumption/ })).toHaveValue(88.508)
    expect(within(incompleteCard).getByText('Estimated 88.508 g = 37% of 239.21 g sliced.')).toBeVisible()
    await user.type(within(incompleteCard).getByRole('textbox', { name: 'Reason (required)' }), 'Cancelled after the base layers')
    expect(screen.getByRole('button', { name: 'Confirm 1 filament' })).toBeEnabled()
  })

  it('requires conscious acknowledgement for a print older than a physical checkpoint', async () => {
    const checkpointQueue = structuredClone(queue)
    checkpointQueue.available_spools[0].latest_physical_calibration_at = '2026-10-06T10:00:00Z'
    checkpointQueue.jobs[0].filaments[0].candidates[0].latest_physical_calibration_at = '2026-10-06T10:00:00Z'
    vi.mocked(fetch).mockImplementation(async (_input, init) => init?.method === 'POST'
      ? response({ reconciled_usage_ids: [501], print_jobs: [] })
      : response(checkpointQueue))
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Select all unambiguous' }))
    expect(screen.getByText(/older than the selected spool’s latest physical calibration/)).toBeVisible()
    const confirm = screen.getByRole('button', { name: 'Confirm 1 filament' })
    expect(confirm).toBeDisabled()
    await user.click(screen.getByLabelText(/I understand this may double-count material/))
    expect(confirm).toBeEnabled()
    await user.click(confirm)
    await waitFor(() => {
      const post = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST')
      expect(JSON.parse(String(post?.[1]?.body)).items[0].checkpoint_acknowledged).toBe(true)
    })
  })
})
