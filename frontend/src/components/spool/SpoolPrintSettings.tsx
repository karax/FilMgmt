import type { Spool } from '../../types/spool'
import { SpoolInfoSection, InfoRow } from './SpoolInfoSection'

function range(min: number | null, max: number | null, unit: string) {
  if (min == null && max == null) return 'Not configured'
  if (min != null && max != null) return `${min}–${max} ${unit}`
  return `${min ?? max} ${unit}`
}

export function SpoolPrintSettings({ spool }: { spool: Spool }) {
  return <SpoolInfoSection title="Print Settings"><InfoRow label="Nozzle temperature">{range(spool.nozzle_temp_min, spool.nozzle_temp_max, '°C')}</InfoRow><InfoRow label="Bed temperature">{range(spool.bed_temp_min, spool.bed_temp_max, '°C')}</InfoRow><InfoRow label="Diameter">{spool.diameter_mm == null ? 'Not configured' : `${spool.diameter_mm} mm`}</InfoRow></SpoolInfoSection>
}
