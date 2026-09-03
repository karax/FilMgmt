import { ArrowLeft, Camera, CameraOff, ScanLine } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { startQrCamera, type QrCameraSession } from '../lib/qrCamera'
import {
  buildSpoolQrLandingPath,
  parseSpoolQrPayload,
} from '../lib/spoolQr'

type CameraState = 'idle' | 'starting' | 'active' | 'error'
type CameraErrorReason = 'secureContext' | 'permissionDenied' | 'noCamera' | 'generic'

const INVALID_SCAN_REPEAT_MS = 2_000

export function QrScannerPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const videoRef = useRef<HTMLVideoElement>(null)
  const sessionRef = useRef<QrCameraSession | null>(null)
  const mountedRef = useRef(true)
  const startInFlightRef = useRef(false)
  const startGenerationRef = useRef(0)
  const resolvedRef = useRef(false)
  const lastInvalidRef = useRef({ value: '', at: 0 })
  const [cameraState, setCameraState] = useState<CameraState>(() => (
    window.isSecureContext === false ? 'error' : 'idle'
  ))
  const [cameraError, setCameraError] = useState<CameraErrorReason | null>(() => (
    window.isSecureContext === false ? 'secureContext' : null
  ))
  const [scanError, setScanError] = useState(false)
  const [manualCode, setManualCode] = useState('')
  const [manualError, setManualError] = useState(false)

  const releaseSession = useCallback(() => {
    sessionRef.current?.stop()
    sessionRef.current = null
  }, [])

  const stopCamera = useCallback(() => {
    startGenerationRef.current += 1
    startInFlightRef.current = false
    releaseSession()
    if (mountedRef.current) {
      setCameraState('idle')
      setCameraError(null)
      setScanError(false)
    }
  }, [releaseSession])

  const navigateToSpool = useCallback((path: string) => {
    if (resolvedRef.current) return
    resolvedRef.current = true
    startGenerationRef.current += 1
    releaseSession()
    navigate(path)
  }, [navigate, releaseSession])

  const handleDecodedValue = useCallback((value: string, stopDecodedSession?: () => void) => {
    if (resolvedRef.current) return

    const code = parseSpoolQrPayload(value)
    const path = code ? buildSpoolQrLandingPath(code) : null
    if (path) {
      stopDecodedSession?.()
      navigateToSpool(path)
      return
    }

    const now = Date.now()
    if (
      lastInvalidRef.current.value === value
      && now - lastInvalidRef.current.at < INVALID_SCAN_REPEAT_MS
    ) return

    lastInvalidRef.current = { value, at: now }
    setScanError(true)
  }, [navigateToSpool])

  const startCamera = useCallback(async () => {
    if (startInFlightRef.current || sessionRef.current) return

    setScanError(false)
    lastInvalidRef.current = { value: '', at: 0 }
    if (window.isSecureContext === false) {
      setCameraState('error')
      setCameraError('secureContext')
      return
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraState('error')
      setCameraError('noCamera')
      return
    }

    const video = videoRef.current
    if (!video) return

    const generation = ++startGenerationRef.current
    startInFlightRef.current = true
    resolvedRef.current = false
    setCameraError(null)
    setCameraState('starting')

    try {
      const session = await startQrCamera(video, handleDecodedValue)
      if (
        !mountedRef.current
        || generation !== startGenerationRef.current
        || resolvedRef.current
      ) {
        session.stop()
        return
      }

      sessionRef.current = session
      setCameraState('active')
    } catch (error) {
      if (!mountedRef.current || generation !== startGenerationRef.current) return
      setCameraState('error')
      setCameraError(cameraErrorReason(error))
    } finally {
      if (generation === startGenerationRef.current) startInFlightRef.current = false
    }
  }, [handleDecodedValue])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      startGenerationRef.current += 1
      releaseSession()
    }
  }, [releaseSession])

  const submitManualCode = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const path = buildSpoolQrLandingPath(manualCode.trim())
    if (!path) {
      setManualError(true)
      return
    }

    setManualError(false)
    navigateToSpool(path)
  }

  const cameraErrorMessage = cameraError ? t(`scan.errors.${cameraError}`) : null

  return (
    <article aria-labelledby="scan-title" className="mx-auto w-full max-w-2xl pb-4">
      <Link
        className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 text-sm font-semibold text-ink-muted transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        to="/inventory"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        {t('scan.back')}
      </Link>

      <header className="mt-5">
        <p className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-accent">
          {t('scan.eyebrow')}
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-ink sm:text-3xl" id="scan-title">
          {t('scan.title')}
        </h2>
        <p className="mt-2 text-sm leading-6 text-ink-muted sm:text-base">
          {t('scan.description')}
        </p>
      </header>

      <section aria-labelledby="camera-title" className="mt-6 rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-5">
        <h2 className="sr-only" id="camera-title">{t('scan.cameraRegion')}</h2>
        <div
          aria-label={t('scan.cameraRegion')}
          className="relative aspect-[4/3] w-full overflow-hidden rounded-lg bg-slate-950 text-white"
          role="img"
        >
          <video
            autoPlay
            className={`size-full object-cover transition-opacity ${cameraState === 'active' ? 'opacity-100' : 'opacity-0'}`}
            muted
            playsInline
            ref={videoRef}
          />

          {cameraState !== 'active' && (
            <div className="absolute inset-0 grid place-items-center px-6 text-center">
              <div>
                {cameraState === 'error'
                  ? <CameraOff aria-hidden="true" className="mx-auto size-9 text-slate-400" />
                  : <Camera aria-hidden="true" className="mx-auto size-9 text-slate-400" />}
                <p className="mt-3 text-sm font-semibold text-slate-200">
                  {cameraState === 'starting' ? t('scan.starting') : t('scan.cameraReadyPrompt')}
                </p>
              </div>
            </div>
          )}

          <div aria-hidden="true" className="pointer-events-none absolute left-1/2 top-1/2 aspect-square w-3/5 max-w-56 -translate-x-1/2 -translate-y-1/2 rounded-xl border-2 border-white/90 shadow-[0_0_0_999px_rgb(0_0_0/0.28)]" />
        </div>

        <div aria-live="polite" className="mt-4 min-h-6">
          {cameraState === 'starting' && <p className="text-sm font-semibold text-ink-muted">{t('scan.starting')}</p>}
          {cameraState === 'active' && <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">{t('scan.active')}</p>}
          {cameraErrorMessage && <p className="text-sm font-semibold text-red-700 dark:text-red-300" role="alert">{cameraErrorMessage}</p>}
          {scanError && <p className="text-sm font-semibold text-amber-800 dark:text-amber-200" role="alert">{t('scan.errors.invalidQr')}</p>}
        </div>

        {cameraState === 'active' ? (
          <button
            className="mt-3 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-line bg-surface-raised px-4 py-2.5 text-sm font-bold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            onClick={stopCamera}
            type="button"
          >
            <CameraOff aria-hidden="true" className="size-4" />
            {t('scan.stop')}
          </button>
        ) : cameraError !== 'secureContext' && (
          <button
            className="mt-3 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-wait disabled:opacity-60"
            disabled={cameraState === 'starting'}
            onClick={() => void startCamera()}
            type="button"
          >
            <Camera aria-hidden="true" className="size-4" />
            {cameraState === 'starting'
              ? t('scan.starting')
              : cameraState === 'error'
                ? t('scan.retry')
                : t('scan.start')}
          </button>
        )}
      </section>

      <div className="my-7 flex items-center gap-3" aria-hidden="true">
        <span className="h-px flex-1 bg-line" />
        <span className="font-mono text-xs font-bold uppercase tracking-[0.14em] text-ink-muted">{t('scan.or')}</span>
        <span className="h-px flex-1 bg-line" />
      </div>

      <section aria-labelledby="manual-code-title" className="rounded-xl border border-line bg-surface p-5 shadow-sm sm:p-6">
        <h2 className="text-lg font-semibold text-ink" id="manual-code-title">{t('scan.manualTitle')}</h2>
        <p className="mt-1 text-sm leading-6 text-ink-muted">{t('scan.manualDescription')}</p>
        <form className="mt-5" onSubmit={submitManualCode}>
          <label className="block text-sm font-semibold text-ink" htmlFor="manual-spool-code">
            {t('scan.spoolCode')}
          </label>
          <input
            aria-describedby={manualError ? 'manual-spool-code-error' : undefined}
            aria-invalid={manualError}
            autoCapitalize="characters"
            autoComplete="off"
            className="mt-2 min-h-12 w-full rounded-md border border-line bg-surface-raised px-3.5 font-mono text-base text-ink outline-none transition-colors placeholder:text-ink-muted/70 focus:border-accent focus:ring-2 focus:ring-accent/20"
            id="manual-spool-code"
            inputMode="text"
            onChange={(event) => {
              setManualCode(event.target.value)
              setManualError(false)
            }}
            placeholder="FIL-0007"
            spellCheck={false}
            value={manualCode}
          />
          {manualError && (
            <p className="mt-2 text-sm font-semibold text-red-700 dark:text-red-300" id="manual-spool-code-error" role="alert">
              {t('scan.errors.invalidCode')}
            </p>
          )}
          <button
            className="mt-4 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-md bg-accent px-5 py-3 text-sm font-bold text-sidebar focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            type="submit"
          >
            <ScanLine aria-hidden="true" className="size-5" />
            {t('scan.openSpool')}
          </button>
        </form>
      </section>
    </article>
  )
}

function cameraErrorReason(error: unknown): CameraErrorReason {
  const name = typeof error === 'object' && error !== null && 'name' in error
    ? String((error as { name: unknown }).name)
    : ''

  if (name === 'NotAllowedError') return 'permissionDenied'
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') return 'noCamera'
  if (name === 'SecurityError') return 'secureContext'
  return 'generic'
}
