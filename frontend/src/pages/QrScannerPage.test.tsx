import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider, useParams } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest'

const camera = vi.hoisted(() => ({
  start: vi.fn(),
}))

vi.mock('../lib/qrCamera', () => ({
  startQrCamera: camera.start,
}))

import i18n from '../i18n'
import { QrScannerPage } from './QrScannerPage'

type DecodeCallback = (value: string, stopSession?: () => void) => void

function LandingDestination() {
  const { code } = useParams()
  return <p>QR landing for {code}</p>
}

function renderPage() {
  const router = createMemoryRouter([
    { path: '/scan', element: <QrScannerPage /> },
    { path: '/qr/spool/:code', element: <LandingDestination /> },
    { path: '/inventory', element: <p>Inventory destination</p> },
  ], { initialEntries: ['/scan'] })

  return {
    router,
    user: userEvent.setup(),
    ...render(<RouterProvider router={router} />),
  }
}

function namedError(name: string): Error {
  const error = new Error(name)
  error.name = name
  return error
}

describe('QrScannerPage', () => {
  let decoded: DecodeCallback | undefined
  let stopSession: Mock<() => void>

  beforeEach(async () => {
    await i18n.changeLanguage('en')
    decoded = undefined
    stopSession = vi.fn<() => void>()
    camera.start.mockReset()
    camera.start.mockImplementation(async (_video, onDecoded: DecodeCallback) => {
      decoded = onDecoded
      return { stop: stopSession }
    })
    Object.defineProperty(window, 'isSecureContext', {
      configurable: true,
      value: true,
    })
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn() },
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('waits for explicit user intent before requesting the camera', () => {
    renderPage()

    expect(screen.getByRole('heading', { name: 'Scan QR' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Start camera' })).toBeEnabled()
    expect(camera.start).not.toHaveBeenCalled()
  })

  it('starts the camera and allows the user to stop it', async () => {
    const { user } = renderPage()

    await user.click(screen.getByRole('button', { name: 'Start camera' }))

    expect(camera.start).toHaveBeenCalledWith(
      expect.any(HTMLVideoElement),
      expect.any(Function),
    )
    expect(await screen.findByText('Camera active. Point it at a spool QR code.')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Stop camera' }))
    expect(stopSession).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Start camera' })).toBeEnabled()
  })

  it('shows an explicit loading state while camera permission is pending', async () => {
    let resolveStart: ((session: { stop: () => void }) => void) | undefined
    camera.start.mockReturnValue(new Promise((resolve) => {
      resolveStart = resolve
    }))
    const { user } = renderPage()

    await user.click(screen.getByRole('button', { name: 'Start camera' }))

    expect(screen.getByRole('button', { name: 'Starting camera...' })).toBeDisabled()
    expect(screen.getAllByText('Starting camera...').length).toBeGreaterThan(1)
    await act(async () => resolveStart?.({ stop: stopSession }))
    expect(await screen.findByRole('button', { name: 'Stop camera' })).toBeEnabled()
  })

  it('uses the canonical parser and navigates a valid QR to its landing page once', async () => {
    const { router, user } = renderPage()
    const navigations: string[] = []
    const unsubscribe = router.subscribe((state) => navigations.push(state.location.pathname))
    await user.click(screen.getByRole('button', { name: 'Start camera' }))
    await screen.findByRole('button', { name: 'Stop camera' })

    act(() => {
      decoded?.('fcc:spool:FIL-0007')
      decoded?.('fcc:spool:FIL-0007')
    })

    await waitFor(() => expect(router.state.location.pathname).toBe('/qr/spool/FIL-0007'))
    expect(screen.getByText('QR landing for FIL-0007')).toBeVisible()
    expect(navigations.filter((path) => path === '/qr/spool/FIL-0007')).toHaveLength(1)
    expect(stopSession).toHaveBeenCalledTimes(1)
    unsubscribe()
  })

  it.each([
    'https://example.com',
    'fcc:material:FIL-0007',
    'fcc:spool:',
  ])('rejects an unrelated QR and keeps scanning: %s', async (value) => {
    const { router, user } = renderPage()
    await user.click(screen.getByRole('button', { name: 'Start camera' }))
    await screen.findByRole('button', { name: 'Stop camera' })

    act(() => decoded?.(value))

    expect(await screen.findByText('This QR code does not belong to a Filament Command Center spool.')).toBeVisible()
    expect(router.state.location.pathname).toBe('/scan')
    expect(screen.getByRole('button', { name: 'Stop camera' })).toBeEnabled()
    expect(stopSession).not.toHaveBeenCalled()
  })

  it.each(['FIL-0007', ' FIL-0007 '])(
    'opens a valid manually entered spool code: %s',
    async (value) => {
      const { router, user } = renderPage()

      await user.type(screen.getByRole('textbox', { name: 'Spool code' }), value)
      await user.click(screen.getByRole('button', { name: 'Open spool' }))

      await waitFor(() => expect(router.state.location.pathname).toBe('/qr/spool/FIL-0007'))
    },
  )

  it('does not navigate for an invalid manual code', async () => {
    const { router, user } = renderPage()

    await user.type(screen.getByRole('textbox', { name: 'Spool code' }), 'INVALID')
    await user.click(screen.getByRole('button', { name: 'Open spool' }))

    expect(screen.getByText('Enter a valid spool code in the FIL-XXXX format.')).toBeVisible()
    expect(router.state.location.pathname).toBe('/scan')
  })

  it('stops the active camera before manual navigation', async () => {
    const { router, user } = renderPage()
    await user.click(screen.getByRole('button', { name: 'Start camera' }))
    await screen.findByRole('button', { name: 'Stop camera' })

    await user.type(screen.getByRole('textbox', { name: 'Spool code' }), 'FIL-9999')
    await user.click(screen.getByRole('button', { name: 'Open spool' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/qr/spool/FIL-9999'))
    expect(stopSession).toHaveBeenCalledTimes(1)
  })

  it('releases the active camera session when the page unmounts', async () => {
    const { unmount, user } = renderPage()
    await user.click(screen.getByRole('button', { name: 'Start camera' }))
    await screen.findByRole('button', { name: 'Stop camera' })

    unmount()

    expect(stopSession).toHaveBeenCalledTimes(1)
  })

  it('releases a camera session that resolves after the page unmounts', async () => {
    let resolveStart: ((session: { stop: () => void }) => void) | undefined
    camera.start.mockReturnValue(new Promise((resolve) => {
      resolveStart = resolve
    }))
    const { unmount, user } = renderPage()
    await user.click(screen.getByRole('button', { name: 'Start camera' }))

    unmount()
    await act(async () => resolveStart?.({ stop: stopSession }))

    expect(stopSession).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['NotAllowedError', 'Camera access was denied.'],
    ['NotFoundError', 'No camera is available.'],
    ['NotReadableError', 'Could not start the camera.'],
  ])('maps %s to a useful camera error', async (name, message) => {
    camera.start.mockRejectedValue(namedError(name))
    const { user } = renderPage()

    await user.click(screen.getByRole('button', { name: 'Start camera' }))

    expect(await screen.findByText(message)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled()
    expect(screen.getByRole('textbox', { name: 'Spool code' })).toBeEnabled()
  })

  it('does not request a camera in an insecure context and preserves manual fallback', () => {
    Object.defineProperty(window, 'isSecureContext', {
      configurable: true,
      value: false,
    })

    renderPage()

    expect(screen.getByText(/Your browser requires a secure connection \(HTTPS\)/)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Start camera' })).not.toBeInTheDocument()
    expect(camera.start).not.toHaveBeenCalled()
    expect(screen.getByRole('textbox', { name: 'Spool code' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Open spool' })).toBeEnabled()
  })

  it('shows no-camera state without calling the adapter when mediaDevices is absent', async () => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: undefined,
    })
    const { user } = renderPage()

    await user.click(screen.getByRole('button', { name: 'Start camera' }))

    expect(screen.getByText('No camera is available.')).toBeVisible()
    expect(camera.start).not.toHaveBeenCalled()
  })

  it('retries successfully after a recoverable camera error', async () => {
    camera.start
      .mockRejectedValueOnce(namedError('NotReadableError'))
      .mockImplementationOnce(async (_video, onDecoded: DecodeCallback) => {
        decoded = onDecoded
        return { stop: stopSession }
      })
    const { user } = renderPage()

    await user.click(screen.getByRole('button', { name: 'Start camera' }))
    await screen.findByText('Could not start the camera.')
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('button', { name: 'Stop camera' })).toBeEnabled()
    expect(camera.start).toHaveBeenCalledTimes(2)
  })

  it('renders scanner and fallback copy in pt-BR', async () => {
    await i18n.changeLanguage('pt-BR')
    renderPage()

    expect(screen.getByRole('heading', { name: 'Escanear QR' })).toBeVisible()
    expect(screen.getByText('Aponte a câmera para a etiqueta do Spool.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Iniciar câmera' })).toBeEnabled()
    expect(screen.getByRole('textbox', { name: 'Código do Spool' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Abrir Spool' })).toBeEnabled()
    expect(screen.getByRole('link', { name: 'Voltar ao Inventário' })).toHaveAttribute('href', '/inventory')
  })

  it('renders scanner and fallback copy in English', () => {
    renderPage()

    expect(screen.getByRole('heading', { name: 'Scan QR' })).toBeVisible()
    expect(screen.getByText('Point the camera at the spool label.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Start camera' })).toBeEnabled()
    expect(screen.getByRole('textbox', { name: 'Spool code' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Open spool' })).toBeEnabled()
    expect(screen.getByRole('link', { name: 'Back to Inventory' })).toHaveAttribute('href', '/inventory')
  })
})
