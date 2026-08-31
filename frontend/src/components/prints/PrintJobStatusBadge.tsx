import { useTranslation } from 'react-i18next'

import type { PrintJobStatus } from '../../types/printJob'

const classes: Record<PrintJobStatus, string> = {
  PLANNED: 'border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300',
  PRINTING: 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200',
  SUCCESS: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
  FAILED: 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300',
  CANCELLED: 'border-line bg-surface-raised text-ink-muted',
}

export function PrintJobStatusBadge({ status }: { status: PrintJobStatus }) {
  const { t } = useTranslation()
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-bold ${classes[status]}`}>{t(`prints.status.${status}`)}</span>
}
