import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import type { BambuStatus } from '../types/bambu'
import { PrinterStatusPage } from './PrinterStatusPage'

const connectedStatus: BambuStatus = {
  configured: true,
  connected: true,
  connection_state: 'CONNECTED',
  missing_configuration: [],
  configuration_error: null,
  serial: 'P1S-TEST-001',
  last_update_at: '2026-10-05T21:15:53Z',
  state: 'PRINTING',
  raw_state: 'RUNNING',
  progress: 42,
  current_layer: 84,
  total_layers: 200,
  remaining_time_minutes: 73,
  current_print: 'Robot Head',
  gcode_file: 'robot_head.gcode.3mf',
  project_name: 'Robot Head',
  project_id: 'project-1',
  profile_id: 'profile-1',
  task_id: 'task-1',
  subtask_id: 'subtask-1',
  current_tray: '1',
  ams: [{
    unit_id: '0', humidity: 2, temperature_c: 45.4,
    trays: [{
      tray_id: '1', material_type: 'PLA', color: 'F98C36FF', profile_id: 'GFL95', setting_id: null,
      brand: 'Bambu Lab', tag_uid: null, tray_uuid: null, remaining_percent: 65, nozzle_temp_min: 190, nozzle_temp_max: 240,
    }],
  }],
  external_tray: null,
  active_print_job_id: 101,
  ftps_configured: true,
  ftps_reachable: true,
  last_ftps_success_at: '2026-10-05T20:10:01Z',
  last_ftps_error_code: null,
}

function apiResponse(data: unknown, ok = true): Response {
  return { ok, status: ok ? 200 : 503, json: vi.fn().mockResolvedValue(data) } as unknown as Response
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter><PrinterStatusPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PrinterStatusPage', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('pt-BR')
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows the live connection, print progress, identifiers, and AMS data', async () => {
    vi.mocked(fetch).mockResolvedValue(apiResponse(connectedStatus))
    renderPage()

    expect(await screen.findByText('P1S conectada')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Status da impressora' })).toBeVisible()
    expect(screen.getByText('Robot Head')).toBeVisible()
    expect(screen.getByText('42%')).toBeVisible()
    expect(screen.getByText('84 / 200')).toBeVisible()
    expect(screen.getByText('task-1')).toBeVisible()
    expect(screen.getByText('Bambu Lab · PLA')).toBeVisible()
    expect(screen.getByText('Selecionado')).toBeVisible()
  })

  it('offers a retry when the diagnostic endpoint is unavailable', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(apiResponse({}, false))
      .mockResolvedValue(apiResponse({ ...connectedStatus, state: 'IDLE', current_print: null, gcode_file: null }))
    renderPage()

    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Tentar novamente' }))
    expect(await screen.findByText('P1S conectada')).toBeVisible()
  })

  it('shows partial telemetry received before gcode_state after a backend restart', async () => {
    vi.mocked(fetch).mockResolvedValue(apiResponse({
      ...connectedStatus,
      state: 'UNKNOWN',
      raw_state: null,
      current_print: null,
      gcode_file: null,
      progress: 41,
      current_layer: 77,
      total_layers: null,
      active_print_job_id: null,
    }))
    renderPage()

    expect(await screen.findByText('41%')).toBeVisible()
    expect(screen.getByText('77')).toBeVisible()
    expect(screen.queryByText('Nenhuma impressão ativa')).not.toBeInTheDocument()
  })
})
