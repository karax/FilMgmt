import type { IScannerControls } from '@zxing/browser'

export const SPOOL_QR_CAMERA_CONSTRAINTS: MediaStreamConstraints = {
  audio: false,
  video: {
    facingMode: { ideal: 'environment' },
  },
}

export interface QrCameraSession {
  stop: () => void
}

export async function startQrCamera(
  video: HTMLVideoElement,
  onDecoded: (value: string, stopSession: () => void) => void,
): Promise<QrCameraSession> {
  const mediaDevices = navigator.mediaDevices
  if (!mediaDevices?.getUserMedia) {
    throw namedError('NotFoundError', 'Camera API unavailable.')
  }

  const stream = await mediaDevices.getUserMedia(SPOOL_QR_CAMERA_CONSTRAINTS)
  let controls: IScannerControls | undefined
  let stopped = false

  const stop = () => {
    if (stopped) return
    stopped = true
    controls?.stop()
    stopMediaStream(stream)
    if (video.srcObject === stream) video.srcObject = null
  }

  try {
    const { BrowserQRCodeReader } = await import('@zxing/browser')
    const reader = new BrowserQRCodeReader(undefined, {
      delayBetweenScanAttempts: 200,
      delayBetweenScanSuccess: 500,
    })
    controls = await reader.decodeFromStream(stream, video, (result) => {
      if (result) onDecoded(result.getText(), stop)
    })
  } catch (error) {
    stop()
    throw error
  }

  if (stopped) controls.stop()
  return { stop }
}

export function stopMediaStream(stream: MediaStream): void {
  for (const track of stream.getTracks()) track.stop()
}

function namedError(name: string, message: string): Error {
  const error = new Error(message)
  error.name = name
  return error
}
