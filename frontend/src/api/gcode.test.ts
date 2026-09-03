import { afterEach, describe, expect, it, vi } from 'vitest'

import { calculateGCodeWeight, detectGCodeMaterial, estimateGCodeTime, parseGCode, uploadGCode } from './gcode'

describe('G-code upload API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('posts one file as FormData without setting a multipart boundary manually', async () => {
    const responsePayload = {
      upload_id: '93e88bde-fcb5-4929-b4a2-50c3d9f201cc',
      filename: 'benchy.gcode',
      size_bytes: 7,
      created_at: '2026-09-01T10:00:00Z',
      status: 'UPLOADED' as const,
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: vi.fn().mockResolvedValue(responsePayload),
    })
    vi.stubGlobal('fetch', fetchMock)
    const file = new File(['G1 X1\n'], 'benchy.gcode')

    await expect(uploadGCode(file)).resolves.toEqual(responsePayload)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(path).toBe('/api/gcode/uploads')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get('file')).toBe(file)
    expect(new Headers(init.headers).has('Content-Type')).toBe(false)
  })

  it('requests parsing for the encoded upload ID without resending the file', async () => {
    const parseResult = {
      parser_version: 1,
      upload_id: '93e88bde-fcb5-4929-b4a2-50c3d9f201cc',
      filename: 'benchy.gcode',
      source_size_bytes: 7,
      line_count: 2,
      blank_line_count: 0,
      comment_line_count: 0,
      command_line_count: 2,
      unknown_line_count: 0,
      malformed_line_count: 0,
      command_counts: { M83: 1, G1: 1 },
      units: 'mm',
      xyz_positioning: 'absolute',
      extrusion_mode: 'relative',
      current_tool: 0,
      tools: [{ tool: 0, extrusion_length_mm: 5, extrusion_volume_mm3: null }],
      total_extrusion_length_mm: 5,
      total_extrusion_volume_mm3: null,
      nozzle_temperatures_c: [],
      bed_temperatures_c: [],
      metadata: {},
      warnings: [],
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(parseResult),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(parseGCode(parseResult.upload_id)).resolves.toEqual(parseResult)

    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(path).toBe(`/api/gcode/uploads/${parseResult.upload_id}/parse`)
    expect(init.method).toBe('POST')
    expect(init).not.toHaveProperty('body')
  })

  it('posts a typed per-tool weight request to the upload endpoint', async () => {
    const payload = {
      tools: [{ tool: 0, material_id: 3, filament_diameter_mm: '1.75' }],
    }
    const responsePayload = {
      upload_id: '93e88bde-fcb5-4929-b4a2-50c3d9f201cc',
      parser_version: 1,
      tools: [],
      total_estimated_weight_g: '2.983',
      known_estimated_weight_g: '2.983',
      is_complete: true,
      warnings: [],
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(responsePayload),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(calculateGCodeWeight(responsePayload.upload_id, payload)).resolves.toEqual(responsePayload)

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/gcode/uploads/${responsePayload.upload_id}/weight`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    )
  })

  it('requests time estimation for the encoded upload ID without a request body', async () => {
    const uploadId = 'time/id'
    const responsePayload = {
      time_estimator_version: 1 as const,
      upload_id: uploadId,
      parser_version: 1,
      estimated_time_seconds: 5423,
      source: 'slicer_metadata' as const,
      slicer_estimated_time_seconds: 5423,
      slicer_time_key: 'time',
      kinematic_estimated_time_seconds: 5178,
      motion_time_seconds: 5100,
      dwell_time_seconds: 78,
      kinematic_is_complete: true,
      unestimated_motion_count: 0,
      is_heuristic: false,
      is_complete: true,
      warnings: [],
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(responsePayload),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(estimateGCodeTime(uploadId)).resolves.toEqual(responsePayload)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/gcode/uploads/time%2Fid/time',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock.mock.calls[0]?.[1]).not.toHaveProperty('body')
  })

  it('requests material detection for the encoded upload ID without a request body', async () => {
    const uploadId = 'material/id'
    const responsePayload = {
      upload_id: uploadId,
      parser_version: 1,
      tools: [],
      is_complete: false,
      warnings: [],
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(responsePayload),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(detectGCodeMaterial(uploadId)).resolves.toEqual(responsePayload)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/gcode/uploads/material%2Fid/material-detection',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock.mock.calls[0]?.[1]).not.toHaveProperty('body')
  })
})
