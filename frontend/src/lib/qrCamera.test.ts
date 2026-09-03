import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const zxing = vi.hoisted(() => ({
  decodeFromStream: vi.fn(),
}))

vi.mock('@zxing/browser', () => ({
  BrowserQRCodeReader: class MockBrowserQrCodeReader {
    decodeFromStream = zxing.decodeFromStream
  },
}))

import {
  SPOOL_QR_CAMERA_CONSTRAINTS,
  startQrCamera,
} from './qrCamera'

function cameraFixture() {
  const stopTrack = vi.fn()
  const stream = {
    getTracks: vi.fn(() => [{ stop: stopTrack }]),
  } as unknown as MediaStream
  const getUserMedia = vi.fn().mockResolvedValue(stream)
  const stopDecoder = vi.fn()
  const video = document.createElement('video')
  Object.defineProperty(video, 'srcObject', {
    configurable: true,
    value: null,
    writable: true,
  })

  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  })
  zxing.decodeFromStream.mockResolvedValue({ stop: stopDecoder })

  return { getUserMedia, stopDecoder, stopTrack, stream, video }
}

describe('QR camera adapter', () => {
  beforeEach(() => {
    zxing.decodeFromStream.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('requests a camera stream with an environment-facing preference', async () => {
    const { getUserMedia, stream, video } = cameraFixture()

    await startQrCamera(video, vi.fn())

    expect(getUserMedia).toHaveBeenCalledWith(SPOOL_QR_CAMERA_CONSTRAINTS)
    expect(getUserMedia).toHaveBeenCalledWith({
      audio: false,
      video: { facingMode: { ideal: 'environment' } },
    })
    expect(zxing.decodeFromStream).toHaveBeenCalledWith(
      stream,
      video,
      expect.any(Function),
    )
  })

  it('forwards decoded text from the local QR reader', async () => {
    const { video } = cameraFixture()
    const onDecoded = vi.fn()

    await startQrCamera(video, onDecoded)
    const decodeCallback = zxing.decodeFromStream.mock.calls[0]?.[2]
    decodeCallback?.({ getText: () => 'fcc:spool:FIL-0007' })

    expect(onDecoded).toHaveBeenCalledWith(
      'fcc:spool:FIL-0007',
      expect.any(Function),
    )
  })

  it('stops decoder controls and every MediaStream track exactly once', async () => {
    const { stopDecoder, stopTrack, stream, video } = cameraFixture()
    Object.defineProperty(video, 'srcObject', { value: stream, writable: true })
    const session = await startQrCamera(video, vi.fn())

    session.stop()
    session.stop()

    expect(stopDecoder).toHaveBeenCalledTimes(1)
    expect(stopTrack).toHaveBeenCalledTimes(1)
    expect(video.srcObject).toBeNull()
  })

  it('releases tracks when decoder startup fails', async () => {
    const { stopTrack, video } = cameraFixture()
    zxing.decodeFromStream.mockRejectedValue(new Error('decoder failed'))

    await expect(startQrCamera(video, vi.fn())).rejects.toThrow('decoder failed')

    expect(stopTrack).toHaveBeenCalledTimes(1)
  })

  it('reports a named no-camera error when mediaDevices is unavailable', async () => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: undefined,
    })

    await expect(startQrCamera(document.createElement('video'), vi.fn()))
      .rejects.toMatchObject({ name: 'NotFoundError' })
  })
})
