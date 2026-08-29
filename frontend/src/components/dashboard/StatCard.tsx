import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string
  subtitle: string
  icon: LucideIcon
  tone?: 'default' | 'warning' | 'danger'
}

const toneClasses = {
  default: 'border-line text-accent',
  warning: 'border-amber-500/35 text-amber-600 dark:text-amber-400',
  danger: 'border-red-500/35 text-red-600 dark:text-red-400',
}

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  tone = 'default',
}: StatCardProps) {
  return (
    <article
      className={`relative overflow-hidden rounded-lg border bg-surface p-4 shadow-sm sm:p-5 ${toneClasses[tone]}`}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted">
          {title}
        </h3>
        <span className="grid size-8 shrink-0 place-items-center rounded-md bg-current/10">
          <Icon aria-hidden="true" className="size-4" strokeWidth={1.8} />
        </span>
      </div>
      <p className="mt-5 break-words text-2xl font-semibold tracking-[-0.035em] text-ink sm:text-[1.7rem]">
        {value}
      </p>
      <p className="mt-1 text-xs leading-5 text-ink-muted">{subtitle}</p>
    </article>
  )
}
