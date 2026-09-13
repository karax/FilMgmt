import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import { GCODE_MAX_UPLOAD_BYTES } from '../lib/gcodeUpload'
import { GCodeUploadPage } from './GCodeUploadPage'

const uploadResponse = {
  upload_id: '93e88bde-fcb5-4929-b4a2-50c3d9f201cc',
  filename: 'Benchy.gcode',
  size_bytes: 7,
  created_at: '2026-09-01T10:00:00Z',
  status: 'UPLOADED',
}

const parseResponse = {
  parser_version: 1,
  upload_id: uploadResponse.upload_id,
  filename: uploadResponse.filename,
  source_size_bytes: 7,
  line_count: 184_532,
  blank_line_count: 20,
  comment_line_count: 5_000,
  command_line_count: 179_210,
  unknown_line_count: 2,
  malformed_line_count: 0,
  command_counts: { G1: 179_000, M104: 2 },
  units: 'mm',
  xyz_positioning: 'absolute',
  extrusion_mode: 'absolute',
  current_tool: 1,
  tools: [
    { tool: 0, extrusion_length_mm: 3_200, extrusion_volume_mm3: null },
    { tool: 1, extrusion_length_mm: 2_221, extrusion_volume_mm3: null },
  ],
  total_extrusion_length_mm: 5_421,
  total_extrusion_volume_mm3: null,
  nozzle_temperatures_c: [210],
  bed_temperatures_c: [60],
  metadata: { layer_height: '0.2' },
  warnings: [],
}

const materialsResponse = [
  {
    id: 3,
    name: 'PLA',
    category: 'PLA',
    default_nozzle_temp_min: 190,
    default_nozzle_temp_max: 220,
    default_bed_temp_min: 0,
    default_bed_temp_max: 60,
    density_g_cm3: '1.240',
    notes: null,
    created_at: '2026-09-01T10:00:00Z',
    updated_at: '2026-09-01T10:00:00Z',
  },
  {
    id: 4,
    name: 'Experimental',
    category: 'OTHER',
    default_nozzle_temp_min: null,
    default_nozzle_temp_max: null,
    default_bed_temp_min: null,
    default_bed_temp_max: null,
    density_g_cm3: null,
    notes: null,
    created_at: '2026-09-01T10:00:00Z',
    updated_at: '2026-09-01T10:00:00Z',
  },
]

const weightResponse = {
  upload_id: uploadResponse.upload_id,
  parser_version: 1,
  tools: [
    {
      tool: 0,
      material_id: 3,
      material_name: 'PLA',
      extrusion_mode: 'linear',
      extrusion_length_mm: '3200.000',
      extrusion_volume_mm3: null,
      calculated_volume_mm3: '7696.902',
      filament_diameter_mm: '1.75',
      diameter_source: 'request',
      density_g_cm3: '1.240',
      density_source: 'material',
      estimated_weight_g: '9.544',
      warnings: [],
    },
    {
      tool: 1,
      material_id: 3,
      material_name: 'PLA',
      extrusion_mode: 'linear',
      extrusion_length_mm: '2221.000',
      extrusion_volume_mm3: null,
      calculated_volume_mm3: '5342.129',
      filament_diameter_mm: '1.75',
      diameter_source: 'request',
      density_g_cm3: '1.240',
      density_source: 'material',
      estimated_weight_g: '6.624',
      warnings: [],
    },
  ],
  total_estimated_weight_g: '16.168',
  known_estimated_weight_g: '16.168',
  is_complete: true,
  warnings: [],
}

const slicerTimeResponse = {
  time_estimator_version: 1,
  upload_id: uploadResponse.upload_id,
  parser_version: 1,
  estimated_time_seconds: 5_423,
  source: 'slicer_metadata',
  slicer_estimated_time_seconds: 5_423,
  slicer_time_key: 'estimated printing time (normal mode)',
  kinematic_estimated_time_seconds: 5_178,
  motion_time_seconds: 5_100,
  dwell_time_seconds: 78,
  kinematic_is_complete: true,
  unestimated_motion_count: 0,
  is_heuristic: false,
  is_complete: true,
  warnings: [],
}

const calculatedTimeResponse = {
  ...slicerTimeResponse,
  estimated_time_seconds: 5_178,
  source: 'command_kinematics',
  slicer_estimated_time_seconds: null,
  slicer_time_key: null,
  is_heuristic: true,
  warnings: ['acceleration_not_modeled', 'temperature_waits_not_modeled'],
}

const unknownMaterialResponse = {
  upload_id: uploadResponse.upload_id,
  parser_version: 1,
  tools: parseResponse.tools.map((tool) => ({
    tool: tool.tool,
    material_id: null,
    material_name: null,
    raw_material_label: null,
    source: null,
    confidence: 'NONE',
    evidence: {
      metadata_key: null,
      nozzle_temperatures_c: [],
      bed_temperatures_c: [],
    },
    candidates: [],
    warnings: ['insufficient_temperature_data'],
  })),
  is_complete: false,
  warnings: ['insufficient_temperature_data'],
}

const metadataMaterialResponse = {
  upload_id: uploadResponse.upload_id,
  parser_version: 1,
  tools: [
    {
      tool: 0,
      material_id: 3,
      material_name: 'PLA',
      raw_material_label: 'PLA',
      source: 'slicer_metadata',
      confidence: 'HIGH',
      evidence: { metadata_key: 'filament_type', nozzle_temperatures_c: [210], bed_temperatures_c: [60] },
      candidates: [],
      warnings: [],
    },
    {
      tool: 1,
      material_id: null,
      material_name: null,
      raw_material_label: null,
      source: null,
      confidence: 'NONE',
      evidence: { metadata_key: null, nozzle_temperatures_c: [], bed_temperatures_c: [] },
      candidates: [],
      warnings: ['insufficient_temperature_data'],
    },
  ],
  is_complete: false,
  warnings: ['insufficient_temperature_data'],
}

let fetchMock: ReturnType<typeof vi.fn>

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  const user = userEvent.setup({ applyAccept: false })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <GCodeUploadPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { user }
}

function successfulResponse(payload: unknown = uploadResponse) {
  return {
    ok: true,
    status: 201,
    json: vi.fn().mockResolvedValue(payload),
  }
}

async function completeUpload(user: ReturnType<typeof userEvent.setup>) {
  const input = screen.getByLabelText(/Select file|Selecionar arquivo/) as HTMLInputElement
  await user.upload(input, new File(['G1 X1\n'], 'Benchy.gcode'))
  await user.click(screen.getByRole('button', { name: /Upload G-code|Enviar G-code/ }))
  return screen.findByRole('button', { name: /Analyze G-code|Analisar G-code/ })
}

function mockGCodeFlow(
  parsePayload: unknown = parseResponse,
  weightPayload: unknown = weightResponse,
  timePayload: unknown = slicerTimeResponse,
  materialPayload: unknown = unknownMaterialResponse,
) {
  fetchMock.mockImplementation((input: string, init?: RequestInit) => {
    if (input === '/api/materials') return Promise.resolve(successfulResponse(materialsResponse))
    if (input.endsWith('/parse')) return Promise.resolve(successfulResponse(parsePayload))
    if (input.endsWith('/weight')) return Promise.resolve(successfulResponse(weightPayload))
    if (input.endsWith('/time')) return Promise.resolve(successfulResponse(timePayload))
    if (input.endsWith('/material-detection')) return Promise.resolve(successfulResponse(materialPayload))
    if (input === '/api/gcode/uploads' && init?.body instanceof FormData) {
      return Promise.resolve(successfulResponse(uploadResponse))
    }
    return Promise.resolve(successfulResponse())
  })
}

async function completeAnalysis(
  user: ReturnType<typeof userEvent.setup>,
  parsePayload: unknown = parseResponse,
  weightPayload: unknown = weightResponse,
  timePayload: unknown = slicerTimeResponse,
  materialPayload: unknown = unknownMaterialResponse,
) {
  mockGCodeFlow(parsePayload, weightPayload, timePayload, materialPayload)
  await completeUpload(user)
  await user.click(screen.getByRole('button', { name: /Analyze G-code|Analisar G-code/ }))
  return screen.findByRole('heading', { name: /Estimated weight|Peso estimado/ })
}

function fileInput() {
  return screen.getByLabelText('Select file') as HTMLInputElement
}

describe('G-code upload page', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en')
    fetchMock = vi.fn().mockResolvedValue(successfulResponse())
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => vi.unstubAllGlobals())

  it('renders the initial upload experience and constrained file input', () => {
    renderPage()

    expect(screen.getByRole('heading', { level: 2, name: 'G-code Analysis' })).toBeVisible()
    expect(screen.getByText('Upload a G-code file for analysis.')).toBeVisible()
    expect(fileInput()).toHaveAttribute('accept', '.gcode')
    expect(screen.getByRole('button', { name: 'Select file' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Upload G-code' })).toBeDisabled()
  })

  it('shows the selected filename and formatted size', async () => {
    const { user } = renderPage()

    await user.upload(fileInput(), new File(['G'.repeat(3.8 * 1024)], 'Benchy.gcode'))

    expect(screen.getByText('Benchy.gcode')).toBeVisible()
    expect(screen.getByText('3.8 KB')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Upload G-code' })).toBeEnabled()
  })

  it('supports dropping one file without making drag and drop mandatory', () => {
    renderPage()
    const file = new File(['G1 X1\n'], 'dropped.gcode')

    fireEvent.drop(screen.getByText('Drop a .gcode file here').parentElement!, {
      dataTransfer: { files: [file] },
    })

    expect(screen.getByText('dropped.gcode')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Select file' })).toBeEnabled()
  })

  it('rejects an invalid extension locally', async () => {
    const { user } = renderPage()

    await user.upload(fileInput(), new File(['mesh'], 'model.stl'))

    expect(screen.getByRole('alert')).toHaveTextContent('Only .gcode files are accepted.')
    expect(screen.getByRole('button', { name: 'Upload G-code' })).toBeDisabled()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('rejects an empty file locally', async () => {
    const { user } = renderPage()

    await user.upload(fileInput(), new File([], 'empty.gcode'))

    expect(screen.getByRole('alert')).toHaveTextContent('The file is empty.')
  })

  it('rejects a file above the configured client limit', async () => {
    const { user } = renderPage()
    const file = new File(['G1'], 'large.gcode')
    Object.defineProperty(file, 'size', { value: GCODE_MAX_UPLOAD_BYTES + 1 })

    await user.upload(fileInput(), file)

    expect(screen.getByRole('alert')).toHaveTextContent(
      'The file exceeds the maximum allowed size.',
    )
  })

  it('uploads valid files through FormData and retains the upload ID in state', async () => {
    const { user } = renderPage()
    await user.upload(fileInput(), new File(['G1 X1\n'], 'Benchy.gcode'))

    await user.click(screen.getByRole('button', { name: 'Upload G-code' }))

    const success = await screen.findByRole('status')
    expect(success).toHaveTextContent('Upload complete')
    expect(success).toHaveTextContent('Benchy.gcode')
    expect(success).toHaveTextContent('File ready for analysis.')
    expect(success).toHaveAttribute('data-upload-id', uploadResponse.upload_id)
    expect(screen.getByRole('button', { name: 'Analyze G-code' })).toBeEnabled()
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get('file')).toBeInstanceOf(File)
  })

  it('blocks double submit while the request is pending', async () => {
    let resolveRequest: ((value: ReturnType<typeof successfulResponse>) => void) | undefined
    fetchMock.mockImplementation(() => new Promise((resolve) => { resolveRequest = resolve }))
    const { user } = renderPage()
    await user.upload(fileInput(), new File(['G1'], 'single.gcode'))
    const uploadButton = screen.getByRole('button', { name: 'Upload G-code' })

    await user.click(uploadButton)

    expect(screen.getByRole('button', { name: 'Uploading...' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Uploading...' }))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    resolveRequest?.(successfulResponse({ ...uploadResponse, filename: 'single.gcode' }))
    await screen.findByText('Upload complete')
  })

  it('shows an API error and retries the same file', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: vi.fn().mockResolvedValue({ detail: 'Storage unavailable.' }),
    })
    const { user } = renderPage()
    await user.upload(fileInput(), new File(['G1'], 'retry.gcode'))
    await user.click(screen.getByRole('button', { name: 'Upload G-code' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not upload the file.')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled()

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    await screen.findByText('Upload complete')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('maps a backend 413 to the size-limit message', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 413,
      json: vi.fn().mockResolvedValue({ detail: 'Too large.' }),
    })
    const { user } = renderPage()
    await user.upload(fileInput(), new File(['G1'], 'server-limit.gcode'))
    await user.click(screen.getByRole('button', { name: 'Upload G-code' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The file exceeds the maximum allowed size.',
    )
  })

  it('shows the structured storage quota error in English', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 507,
      json: vi.fn().mockResolvedValue({
        detail: {
          code: 'gcode_storage_quota_exceeded',
          message: 'G-code storage has reached its configured limit.',
        },
      }),
    })
    const { user } = renderPage()
    await user.upload(fileInput(), new File(['G1'], 'quota.gcode'))
    await user.click(screen.getByRole('button', { name: 'Upload G-code' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('G-code storage has reached its configured limit.')
    expect(alert).not.toHaveTextContent('Could not upload the file.')
  })

  it('shows the structured storage quota error in pt-BR', async () => {
    await i18n.changeLanguage('pt-BR')
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 507,
      json: vi.fn().mockResolvedValue({
        detail: {
          code: 'gcode_storage_quota_exceeded',
          message: 'G-code storage has reached its configured limit.',
        },
      }),
    })
    const { user } = renderPage()
    const input = screen.getByLabelText('Selecionar arquivo') as HTMLInputElement
    await user.upload(input, new File(['G1'], 'quota.gcode'))
    await user.click(screen.getByRole('button', { name: 'Enviar G-code' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('O armazenamento de G-code atingiu o limite configurado.')
    expect(alert).not.toHaveTextContent('Não foi possível enviar o arquivo.')
  })

  it('allows selecting a new file after an upload error', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: vi.fn().mockResolvedValue(null),
    })
    const { user } = renderPage()
    await user.upload(fileInput(), new File(['G1'], 'failed.gcode'))
    await user.click(screen.getByRole('button', { name: 'Upload G-code' }))
    await screen.findByRole('alert')

    await user.upload(fileInput(), new File(['G2'], 'replacement.gcode'))

    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    expect(screen.getByText('replacement.gcode')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Upload G-code' })).toBeEnabled()
  })

  it('calls the parse endpoint for the retained upload ID and shows the generic summary', async () => {
    fetchMock
      .mockResolvedValueOnce(successfulResponse())
      .mockResolvedValueOnce(successfulResponse(parseResponse))
    const { user } = renderPage()
    await completeUpload(user)

    await user.click(screen.getByRole('button', { name: 'Analyze G-code' }))

    const summary = await screen.findByRole('region', { name: 'File analyzed' })
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `/api/gcode/uploads/${uploadResponse.upload_id}/parse`,
      expect.objectContaining({ method: 'POST' }),
    )
    expect(summary).toHaveTextContent('Lines')
    expect(summary).toHaveTextContent('184,532')
    expect(summary).toHaveTextContent('Commands')
    expect(summary).toHaveTextContent('179,210')
    expect(summary).toHaveTextContent('Detected extruders')
    expect(summary).toHaveTextContent('2')
    expect(summary).toHaveTextContent('Extrusion length')
    expect(summary).toHaveTextContent('5.42 m')
    expect(summary).toHaveTextContent('T0')
    expect(summary).toHaveTextContent('T1')
    expect(summary).not.toHaveTextContent(/weight|print time|material/i)
  })

  it('shows volumetric extrusion in mm³ without a false linear metric', async () => {
    const volumetric = {
      ...parseResponse,
      tools: [{ tool: 0, extrusion_length_mm: null, extrusion_volume_mm3: 42.5 }],
      total_extrusion_length_mm: null,
      total_extrusion_volume_mm3: 42.5,
      warnings: ['volumetric_extrusion_detected'],
    }
    fetchMock
      .mockResolvedValueOnce(successfulResponse())
      .mockResolvedValueOnce(successfulResponse(volumetric))
    const { user } = renderPage()
    await completeUpload(user)

    await user.click(screen.getByRole('button', { name: 'Analyze G-code' }))

    const summary = await screen.findByRole('region', { name: 'File analyzed' })
    expect(summary).toHaveTextContent('Volumetric extrusion')
    expect(summary).toHaveTextContent('42.5 mm³')
    expect(summary).not.toHaveTextContent('Extrusion length')
    expect(summary).toHaveTextContent('Volumetric extrusion commands were detected.')
  })

  it('blocks duplicate analysis requests while parsing', async () => {
    let resolveParse: ((value: ReturnType<typeof successfulResponse>) => void) | undefined
    fetchMock
      .mockResolvedValueOnce(successfulResponse())
      .mockImplementationOnce(() => new Promise((resolve) => { resolveParse = resolve }))
    const { user } = renderPage()
    await completeUpload(user)

    await user.click(screen.getByRole('button', { name: 'Analyze G-code' }))

    const pendingButton = screen.getByRole('button', { name: 'Analyzing G-code...' })
    expect(pendingButton).toBeDisabled()
    await user.click(pendingButton)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    resolveParse?.(successfulResponse(parseResponse))
    await screen.findByRole('region', { name: 'File analyzed' })
  })

  it('retries parsing with the same upload ID without uploading again', async () => {
    fetchMock
      .mockResolvedValueOnce(successfulResponse())
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: vi.fn().mockResolvedValue({ detail: 'Parse failed.' }),
      })
      .mockResolvedValueOnce(successfulResponse(parseResponse))
    const { user } = renderPage()
    await completeUpload(user)
    await user.click(screen.getByRole('button', { name: 'Analyze G-code' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not analyze this G-code file.',
    )
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    await screen.findByRole('region', { name: 'File analyzed' })
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/parse'))).toHaveLength(2)
    expect(fetchMock.mock.calls.filter(([, init]) => init?.body instanceof FormData)).toHaveLength(1)
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      `/api/gcode/uploads/${uploadResponse.upload_id}/parse`,
    )
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/parse'))[1]?.[0]).toBe(
      `/api/gcode/uploads/${uploadResponse.upload_id}/parse`,
    )
  })

  it('renders pt-BR translations', async () => {
    await i18n.changeLanguage('pt-BR')
    renderPage()

    expect(screen.getByRole('heading', { name: 'Analisar G-code' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Selecionar arquivo' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Enviar G-code' })).toBeDisabled()
  })

  it('renders the analysis flow in pt-BR', async () => {
    await i18n.changeLanguage('pt-BR')
    fetchMock.mockResolvedValueOnce(successfulResponse())
    const { user } = renderPage()
    await user.upload(screen.getByLabelText('Selecionar arquivo'), new File(['G1'], 'modelo.gcode'))
    await user.click(screen.getByRole('button', { name: 'Enviar G-code' }))

    expect(await screen.findByRole('button', { name: 'Analisar G-code' })).toBeEnabled()
  })

  it('renders English translations', () => {
    renderPage()

    expect(screen.getByRole('heading', { name: 'G-code Analysis' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Select file' })).toBeEnabled()
  })

  it('renders per-tool material and visible diameter inputs after analysis', async () => {
    const { user } = renderPage()
    await completeAnalysis(user)

    expect(screen.getAllByRole('group')).toHaveLength(2)
    expect(screen.getByLabelText('Material T0')).toHaveTextContent('PLA')
    expect(screen.getByLabelText('Material T1')).toHaveTextContent('Experimental')
    expect(screen.getByLabelText('Filament diameter T0')).toHaveValue(1.75)
    expect(screen.getByLabelText('Filament diameter T1')).toHaveValue(1.75)
    expect(screen.getByRole('button', { name: 'Calculate weight' })).toBeEnabled()
  })

  it('prefills metadata diameter and does not require diameter for volumetric tools', async () => {
    const mixedTools = {
      ...parseResponse,
      tools: [
        { tool: 0, extrusion_length_mm: 1000, extrusion_volume_mm3: null },
        { tool: 1, extrusion_length_mm: null, extrusion_volume_mm3: 1000 },
      ],
      metadata: { filament_diameter: '2.85,1.75' },
    }
    const { user } = renderPage()
    await completeAnalysis(user, mixedTools)

    expect(screen.getByLabelText('Filament diameter T0')).toHaveValue(2.85)
    expect(screen.queryByLabelText('Filament diameter T1')).not.toBeInTheDocument()
    expect(screen.getByText('This G-code uses volumetric extrusion.')).toBeVisible()
  })

  it('sends one configuration per tool and renders the complete estimated total', async () => {
    const { user } = renderPage()
    await completeAnalysis(user)
    await user.selectOptions(screen.getByLabelText('Material T0'), '3')
    await user.selectOptions(screen.getByLabelText('Material T1'), '3')

    await user.click(screen.getByRole('button', { name: 'Calculate weight' }))

    const result = await screen.findByRole('region', { name: 'Estimated weight result' })
    const weightCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/weight'))
    expect(weightCall?.[0]).toBe(`/api/gcode/uploads/${uploadResponse.upload_id}/weight`)
    expect(JSON.parse(String(weightCall?.[1]?.body))).toEqual({
      tools: [
        { tool: 0, material_id: 3, filament_diameter_mm: '1.75' },
        { tool: 1, material_id: 3, filament_diameter_mm: '1.75' },
      ],
    })
    expect(result).toHaveTextContent('Estimated total')
    expect(result).toHaveTextContent('16.17 g')
    expect(result).toHaveTextContent('T0 — PLA')
    expect(result).toHaveTextContent('T1 — PLA')
  })

  it('blocks duplicate calculation and labels a partial result as known weight', async () => {
    let resolveWeight: ((value: ReturnType<typeof successfulResponse>) => void) | undefined
    const partial = {
      ...weightResponse,
      tools: [weightResponse.tools[0], { ...weightResponse.tools[1], material_id: null, material_name: null, estimated_weight_g: null, density_g_cm3: null, density_source: 'not_available' }],
      total_estimated_weight_g: null,
      known_estimated_weight_g: '9.544',
      is_complete: false,
      warnings: ['missing_density', 'incomplete_weight_estimate'],
    }
    mockGCodeFlow(parseResponse, partial)
    fetchMock.mockImplementation((input: string, init?: RequestInit) => {
      if (input.endsWith('/weight')) return new Promise((resolve) => { resolveWeight = resolve })
      if (input === '/api/materials') return Promise.resolve(successfulResponse(materialsResponse))
      if (input.endsWith('/parse')) return Promise.resolve(successfulResponse(parseResponse))
      if (input.endsWith('/time')) return Promise.resolve(successfulResponse(slicerTimeResponse))
      if (input.endsWith('/material-detection')) return Promise.resolve(successfulResponse(unknownMaterialResponse))
      if (input === '/api/gcode/uploads' && init?.body instanceof FormData) return Promise.resolve(successfulResponse(uploadResponse))
      return Promise.resolve(successfulResponse())
    })
    const { user } = renderPage()
    await completeUpload(user)
    await user.click(screen.getByRole('button', { name: 'Analyze G-code' }))
    await screen.findByRole('heading', { name: 'Estimated weight' })

    await user.click(screen.getByRole('button', { name: 'Calculate weight' }))
    expect(screen.getByRole('button', { name: 'Calculating...' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Calculating...' }))
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/weight'))).toHaveLength(1)
    resolveWeight?.(successfulResponse(partial))

    const result = await screen.findByRole('region', { name: 'Estimated weight result' })
    expect(result).toHaveTextContent('Known weight')
    expect(result).not.toHaveTextContent('Estimated total')
    expect(result).toHaveTextContent('Could not calculate the weight of every extruder.')
  })

  it('renders weight controls in pt-BR and exposes unavailable material density', async () => {
    await i18n.changeLanguage('pt-BR')
    const { user } = renderPage()
    await completeAnalysis(user)

    await user.selectOptions(screen.getByLabelText('Material T0'), '4')
    expect(screen.getByText('Densidade não disponível.')).toBeVisible()
    expect(screen.getByLabelText('Diâmetro do filamento T0')).toHaveValue(1.75)
    expect(screen.getByRole('button', { name: 'Calcular peso' })).toBeEnabled()
  })

  it('shows HIGH slicer metadata and safely prefills the matching weight material', async () => {
    const { user } = renderPage()
    await completeAnalysis(user, parseResponse, weightResponse, slicerTimeResponse, metadataMaterialResponse)

    const result = await screen.findByRole('region', { name: 'Material detection result' })
    expect(result).toHaveTextContent('Detected material')
    expect(result).toHaveTextContent('PLA')
    expect(result).toHaveTextContent('High')
    expect(result).toHaveTextContent('Slicer metadata')
    await waitFor(() => expect(screen.getByLabelText('Material T0')).toHaveValue('3'))
    expect(screen.getByLabelText('Material T1')).toHaveValue('')
  })

  it('shows ambiguous temperature candidates without auto-selecting a material', async () => {
    const ambiguous = {
      ...unknownMaterialResponse,
      tools: [{
        ...unknownMaterialResponse.tools[0],
        source: 'temperature_heuristic',
        confidence: 'LOW',
        evidence: { metadata_key: null, nozzle_temperatures_c: [210], bed_temperatures_c: [60] },
        candidates: [
          { material_id: 3, material_name: 'PLA' },
          { material_id: 8, material_name: 'PLA+' },
        ],
        warnings: ['ambiguous_material'],
      }, unknownMaterialResponse.tools[1]],
      warnings: ['ambiguous_material'],
    }
    const { user } = renderPage()
    await completeAnalysis(user, parseResponse, weightResponse, slicerTimeResponse, ambiguous)

    const result = await screen.findByRole('region', { name: 'Material detection result' })
    expect(result).toHaveTextContent('Possible materials')
    expect(result).toHaveTextContent('PLA, PLA+')
    expect(result).toHaveTextContent('Low')
    expect(result).toHaveTextContent('G-code temperatures')
    expect(screen.getByLabelText('Material T0')).toHaveValue('')
  })

  it('does not auto-select a MEDIUM temperature result', async () => {
    const medium = {
      ...unknownMaterialResponse,
      tools: [{
        ...metadataMaterialResponse.tools[0],
        source: 'temperature_heuristic',
        confidence: 'MEDIUM',
        raw_material_label: null,
        evidence: { metadata_key: null, nozzle_temperatures_c: [210], bed_temperatures_c: [60] },
      }, unknownMaterialResponse.tools[1]],
    }
    const { user } = renderPage()
    await completeAnalysis(user, parseResponse, weightResponse, slicerTimeResponse, medium)

    expect(await screen.findByText('Probable material')).toBeVisible()
    expect(screen.getByLabelText('Material T0')).toHaveValue('')
  })

  it('never overwrites a manual weight material selection when detection finishes later', async () => {
    let resolveDetection: ((value: ReturnType<typeof successfulResponse>) => void) | undefined
    fetchMock.mockImplementation((input: string, init?: RequestInit) => {
      if (input === '/api/materials') return Promise.resolve(successfulResponse(materialsResponse))
      if (input.endsWith('/parse')) return Promise.resolve(successfulResponse(parseResponse))
      if (input.endsWith('/weight')) return Promise.resolve(successfulResponse(weightResponse))
      if (input.endsWith('/time')) return Promise.resolve(successfulResponse(slicerTimeResponse))
      if (input.endsWith('/material-detection')) {
        return new Promise((resolve) => { resolveDetection = resolve })
      }
      if (input === '/api/gcode/uploads' && init?.body instanceof FormData) {
        return Promise.resolve(successfulResponse(uploadResponse))
      }
      return Promise.resolve(successfulResponse())
    })
    const { user } = renderPage()
    await completeUpload(user)
    await user.click(screen.getByRole('button', { name: 'Analyze G-code' }))
    await screen.findByRole('heading', { name: 'Estimated weight' })
    await user.selectOptions(screen.getByLabelText('Material T0'), '4')

    resolveDetection?.(successfulResponse(metadataMaterialResponse))

    await screen.findByRole('region', { name: 'Material detection result' })
    expect(screen.getByLabelText('Material T0')).toHaveValue('4')
  })

  it('preserves an explicit raw label missing from the catalog without prefilling weight', async () => {
    const missingCatalog = {
      ...metadataMaterialResponse,
      tools: [{
        ...metadataMaterialResponse.tools[0],
        material_id: null,
        material_name: null,
        raw_material_label: 'SuperPLA Xtreme',
        warnings: ['explicit_material_not_in_catalog'],
      }, metadataMaterialResponse.tools[1]],
      warnings: ['explicit_material_not_in_catalog'],
    }
    const { user } = renderPage()
    await completeAnalysis(user, parseResponse, weightResponse, slicerTimeResponse, missingCatalog)

    const result = await screen.findByRole('region', { name: 'Material detection result' })
    expect(result).toHaveTextContent('SuperPLA Xtreme')
    expect(result).toHaveTextContent('not in the catalog')
    expect(screen.getByLabelText('Material T0')).toHaveValue('')
  })

  it('renders per-tool detection and pt-BR labels alongside weight and time', async () => {
    await i18n.changeLanguage('pt-BR')
    const multiTool = {
      ...metadataMaterialResponse,
      tools: [
        metadataMaterialResponse.tools[0],
        {
          ...metadataMaterialResponse.tools[0],
          tool: 1,
          material_id: 4,
          material_name: 'Experimental',
          raw_material_label: 'Experimental',
        },
      ],
      is_complete: true,
      warnings: [],
    }
    const { user } = renderPage()
    await completeAnalysis(user, parseResponse, weightResponse, slicerTimeResponse, multiTool)

    const result = await screen.findByRole('region', { name: 'Resultado da detecção de material' })
    expect(screen.getByRole('heading', { name: 'Detecção de material' })).toBeVisible()
    expect(result).toHaveTextContent('T0')
    expect(result).toHaveTextContent('T1')
    expect(result).toHaveTextContent('PLA')
    expect(result).toHaveTextContent('Experimental')
    expect(result).toHaveTextContent('Alta')
    expect(result).toHaveTextContent('Metadata do slicer')
    expect(screen.getByRole('heading', { name: 'Peso estimado' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Tempo estimado' })).toBeVisible()
  })

  it('shows the slicer time source after analysis without kinematic warning noise', async () => {
    const { user } = renderPage()
    await completeAnalysis(user)

    const result = await screen.findByRole('region', { name: 'Estimated time result' })
    expect(result).toHaveTextContent('1 hr 30 min')
    expect(result).toHaveTextContent('Slicer estimate')
    expect(result).not.toHaveTextContent('Printer acceleration was not included.')
    expect(screen.getByRole('heading', { name: 'Estimated weight' })).toBeVisible()
  })

  it('marks command timing as approximate and shows compact relevant warnings', async () => {
    const { user } = renderPage()
    await completeAnalysis(user, parseResponse, weightResponse, calculatedTimeResponse)

    const result = await screen.findByRole('region', { name: 'Estimated time result' })
    expect(result).toHaveTextContent('~1 hr 26 min')
    expect(result).toHaveTextContent('Calculated estimate')
    expect(result).toHaveTextContent('Printer acceleration was not included.')
    expect(result).toHaveTextContent('Heating time was not included.')
  })

  it('formats durations over 24 hours without wrapping', async () => {
    const { user } = renderPage()
    await completeAnalysis(user, parseResponse, weightResponse, {
      ...slicerTimeResponse,
      estimated_time_seconds: 98_400,
      slicer_estimated_time_seconds: 98_400,
    })

    expect(await screen.findByRole('region', { name: 'Estimated time result' }))
      .toHaveTextContent('1 d 3 hr 20 min')
  })

  it('preserves a null estimate and explains that it is unavailable', async () => {
    const { user } = renderPage()
    await completeAnalysis(user, parseResponse, weightResponse, {
      ...calculatedTimeResponse,
      estimated_time_seconds: null,
      source: null,
      kinematic_estimated_time_seconds: null,
      is_heuristic: false,
      is_complete: false,
      warnings: ['missing_feedrate'],
    })

    const result = await screen.findByRole('region', { name: 'Estimated time result' })
    expect(result).toHaveTextContent('—')
    expect(result).toHaveTextContent('Could not estimate the time for this G-code.')
  })

  it('renders the time result in pt-BR', async () => {
    await i18n.changeLanguage('pt-BR')
    const { user } = renderPage()
    await completeAnalysis(user, parseResponse, weightResponse, calculatedTimeResponse)

    const result = await screen.findByRole('region', { name: 'Resultado do tempo estimado' })
    expect(screen.getByRole('heading', { name: 'Tempo estimado' })).toBeVisible()
    expect(result).toHaveTextContent('~1 h 26 min')
    expect(result).toHaveTextContent('Estimativa calculada')
    expect(result).toHaveTextContent('A aceleração da impressora não foi considerada.')
  })
})
