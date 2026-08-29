import type { SpoolStatus } from '../../types/spool'

interface StatusBadgeProps {
  status: SpoolStatus
}

const statusClasses: Record<SpoolStatus, string> = {
  SEALED: 'border-cyan-500/35 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300',
  OPEN: 'border-teal-500/35 bg-teal-500/10 text-teal-700 dark:text-teal-300',
  IN_USE: 'border-blue-500/35 bg-blue-500/10 text-blue-700 dark:text-blue-300',
  LOW: 'border-amber-500/35 bg-amber-500/10 text-amber-700 dark:text-amber-300',
  EMPTY: 'border-red-500/35 bg-red-500/10 text-red-700 dark:text-red-300',
  NEEDS_DRYING:
    'border-sky-500/35 bg-sky-500/10 text-sky-700 dark:text-sky-300',
  ARCHIVED: 'border-slate-500/35 bg-slate-500/10 text-slate-700 dark:text-slate-300',
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex rounded border px-2 py-1 font-mono text-[0.62rem] font-bold tracking-[0.09em] ${statusClasses[status]}`}
    >
      {status}
    </span>
  )
}
