import { formatPercent } from '../../lib/inventory'
import { useTranslation } from 'react-i18next'

interface SpoolProgressBarProps {
  remainingPercent: number
  label: string
  remainingLabel?: string
  accessibleLabel?: string
}

function clampPercent(percent: number): number {
  return Math.min(100, Math.max(0, percent))
}

export function SpoolProgressBar({
  remainingPercent,
  label,
  remainingLabel,
  accessibleLabel,
}: SpoolProgressBarProps) {
  const { t } = useTranslation()
  const clampedPercent = clampPercent(remainingPercent)
  const formattedPercent = formatPercent(clampedPercent)

  return (
    <div>
      <div className="flex items-end justify-between gap-4">
        <span className="font-mono text-xs font-semibold uppercase tracking-[0.1em] text-ink-muted">
          {remainingLabel ?? t('inventory.remaining')}
        </span>
        <span className="font-mono text-sm font-semibold text-ink">
          {formattedPercent}
        </span>
      </div>
      <div
        aria-label={accessibleLabel ?? t('spool.remainingAria', { code: label })}
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={clampedPercent}
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-line"
        role="progressbar"
      >
        <div
          className="h-full rounded-full bg-accent"
          style={{ width: `${clampedPercent}%` }}
        />
      </div>
    </div>
  )
}
