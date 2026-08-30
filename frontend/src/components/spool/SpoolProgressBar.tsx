import { formatPercent } from '../../lib/inventory'

interface SpoolProgressBarProps {
  remainingPercent: number
  label: string
}

function clampPercent(percent: number): number {
  return Math.min(100, Math.max(0, percent))
}

export function SpoolProgressBar({
  remainingPercent,
  label,
}: SpoolProgressBarProps) {
  const clampedPercent = clampPercent(remainingPercent)

  return (
    <div>
      <div className="flex items-end justify-between gap-4">
        <span className="font-mono text-xs font-semibold uppercase tracking-[0.1em] text-ink-muted">
          Remaining
        </span>
        <span className="font-mono text-sm font-semibold text-ink">
          {formatPercent(clampedPercent)}
        </span>
      </div>
      <div
        aria-label={`${label} remaining filament`}
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
