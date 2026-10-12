import i18n from '../i18n'
import type { PrintJob, PrintJobStatus } from '../types/printJob'

function locale(): string { return i18n.language === 'en' ? 'en-US' : 'pt-BR' }

export function formatDuration(minutes: number | null): string {
  if (minutes == null) return '—'
  const hours = Math.floor(minutes / 60)
  const remainder = minutes % 60
  if (hours === 0) return `${minutes} min`
  return remainder === 0 ? `${hours}h` : `${hours}h ${remainder}min`
}

export function formatPrintDateTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(locale(), {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(date)
}

export function elapsedMinutes(startedAt: string | null, now = Date.now()): number | null {
  if (!startedAt) return null
  const started = new Date(startedAt).getTime()
  if (!Number.isFinite(started) || started > now) return null
  return Math.floor((now - started) / 60_000)
}

export const printJobStatuses: readonly PrintJobStatus[] = ['PRINTING', 'PAUSED', 'PLANNED', 'SUCCESS', 'COMPLETED', 'FAILED', 'CANCELLED', 'UNKNOWN_TERMINAL']

export function jobsForStatus(jobs: PrintJob[], status: PrintJobStatus): PrintJob[] {
  const dateFor = (job: PrintJob) => status === 'PRINTING' || status === 'PAUSED' ? job.started_at : status === 'SUCCESS' || status === 'COMPLETED' ? job.finished_at : job.created_at
  return jobs
    .filter((job) => job.status === status)
    .sort((left, right) => (dateFor(right) ?? right.created_at).localeCompare(dateFor(left) ?? left.created_at) || right.id - left.id)
}
