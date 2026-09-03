import { Download } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { useRef } from 'react'
import { useTranslation } from 'react-i18next'

import { buildSpoolQrPayload, downloadSpoolQrSvg } from '../../lib/spoolQr'

export function SpoolQrCard({ code, displayName }: { code: string | null | undefined; displayName: string | null }) {
  const { t } = useTranslation()
  const qrRef = useRef<SVGSVGElement>(null)
  const payload = buildSpoolQrPayload(code)

  if (!payload || !code) return null

  return (
    <section aria-labelledby="spool-qr-title" className="rounded-lg border border-line bg-surface p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-ink" id="spool-qr-title">{t('spool.qr.title')}</h2>
      <p className="mt-1 text-sm leading-6 text-ink-muted">{t('spool.qr.description')}</p>
      <div className="mt-5 flex flex-col items-center">
        <div className="w-full max-w-[220px] overflow-hidden rounded-lg bg-white shadow-sm ring-1 ring-black/10">
          <QRCodeSVG
            aria-label={t('spool.qr.accessible', { code })}
            bgColor="#ffffff"
            className="block h-auto w-full"
            data-qr-payload={payload}
            fgColor="#000000"
            level="M"
            marginSize={4}
            ref={qrRef}
            role="img"
            size={220}
            title={payload}
            value={payload}
          />
        </div>
        <div className="mt-4 text-center">
          {displayName && <p className="text-sm font-semibold text-ink">{displayName}</p>}
          <p className={`${displayName ? 'mt-1' : ''} font-mono text-sm font-bold tracking-[0.1em] text-ink`}>{code}</p>
        </div>
        <button
          className="mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-bold text-sidebar transition-colors hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:w-auto"
          onClick={() => { if (qrRef.current) downloadSpoolQrSvg(qrRef.current, code) }}
          type="button"
        >
          <Download aria-hidden="true" className="size-4" />
          {t('spool.qr.download')}
        </button>
      </div>
    </section>
  )
}
