import { Image as ImageIcon } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

type PrintJobThumbnailProps = {
  alt: string
  className?: string
  url: string | null | undefined
}

export function PrintJobThumbnail({ alt, className = '', url }: PrintJobThumbnailProps) {
  const { t } = useTranslation()
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  const showImage = Boolean(url) && failedUrl !== url

  return (
    <div className={`grid shrink-0 place-items-center overflow-hidden rounded-lg border border-line bg-surface-raised ${className}`}>
      {showImage ? (
        <img alt={alt} className="size-full object-contain" loading="lazy" onError={() => setFailedUrl(url!)} src={url!} />
      ) : (
        <div className="flex flex-col items-center gap-2 px-3 text-center text-ink-muted">
          <ImageIcon aria-hidden="true" className="size-6" />
          <span className="text-[0.68rem] font-medium">{t('prints.metadata.noThumbnail')}</span>
        </div>
      )}
    </div>
  )
}

export function filamentColor(value: string | null): string | undefined {
  if (!value) return undefined
  const normalized = value.startsWith('#') ? value : `#${value}`
  return /^#[0-9a-f]{6}(?:[0-9a-f]{2})?$/i.test(normalized) ? normalized.slice(0, 7) : undefined
}
