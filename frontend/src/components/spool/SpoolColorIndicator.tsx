import { useTranslation } from 'react-i18next'

interface SpoolColorIndicatorProps {
  colorHex: string | null
  colorName: string
  className?: string
}

export function SpoolColorIndicator({
  colorHex,
  colorName,
  className = '',
}: SpoolColorIndicatorProps) {
  const { t } = useTranslation()

  return (
    <span
      aria-label={t('spool.colorAria', { color: colorName })}
      className={`size-3.5 shrink-0 rounded-full border border-black/15 shadow-sm dark:border-white/20 ${
        colorHex ? '' : 'bg-line'
      } ${className}`}
      style={colorHex ? { backgroundColor: colorHex } : undefined}
    />
  )
}
