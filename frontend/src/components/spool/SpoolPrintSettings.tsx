import type { Spool } from '../../types/spool'
import { useTranslation } from 'react-i18next'
import { SpoolInfoSection, InfoRow } from './SpoolInfoSection'

function range(min: number | null, max: number | null, unit: string, unconfigured: string) {
  if (min == null && max == null) return unconfigured
  if (min != null && max != null) return `${min}–${max} ${unit}`
  return `${min ?? max} ${unit}`
}

export function SpoolPrintSettings({ spool }: { spool: Spool }) {
  const { t } = useTranslation()
  return <SpoolInfoSection title={t('spool.printSettings')}><InfoRow label={t('spool.nozzleTemperature')}>{range(spool.nozzle_temp_min, spool.nozzle_temp_max, '°C', t('common.unconfigured'))}</InfoRow><InfoRow label={t('spool.bedTemperature')}>{range(spool.bed_temp_min, spool.bed_temp_max, '°C', t('common.unconfigured'))}</InfoRow><InfoRow label={t('spool.diameterLabel')}>{spool.diameter_mm == null ? t('common.unconfigured') : `${spool.diameter_mm} mm`}</InfoRow></SpoolInfoSection>
}
