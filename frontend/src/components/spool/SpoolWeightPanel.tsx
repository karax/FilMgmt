import { formatWeight } from '../../lib/inventory'
import type { Spool } from '../../types/spool'
import { SpoolProgressBar } from './SpoolProgressBar'

export function SpoolWeightPanel({ spool }: { spool: Spool }) {
  return (
    <section aria-labelledby="weight-title" className="rounded-lg border border-line bg-surface p-5 shadow-sm">
      <h2 id="weight-title" className="text-lg font-semibold text-ink">Weight</h2>
      <div className="mt-5 grid grid-cols-2 gap-4">
        <Metric label="Current weight" value={formatWeight(Number(spool.current_filament_weight_g))} />
        <Metric label="Initial weight" value={formatWeight(Number(spool.initial_filament_weight_g))} />
      </div>
      <div className="mt-5"><SpoolProgressBar label={spool.code} remainingPercent={spool.remaining_percent} /></div>
      <div className="mt-5 border-t border-line pt-4"><Metric label="Empty spool weight" value={spool.empty_spool_weight_g == null ? 'Not configured' : formatWeight(Number(spool.empty_spool_weight_g))} /></div>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</dt><dd className="mt-1 text-lg font-semibold text-ink">{value}</dd></div>
}
