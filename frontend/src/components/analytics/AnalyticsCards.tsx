import type { LucideIcon } from 'lucide-react'
import { ArrowUpRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function KpiCard({
  title,
  value,
  subtitle,
  icon: Icon,
  tone = 'default',
  to,
}: {
  title: string
  value: string
  subtitle: string
  icon: LucideIcon
  tone?: 'default' | 'attention'
  to?: string
}) {
  const content = (
    <>
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-ink-muted">{title}</h3>
        <span className={`grid size-8 shrink-0 place-items-center rounded-md ${tone === 'attention' ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400' : 'bg-accent-soft text-accent'}`}>
          <Icon aria-hidden="true" className="size-4" strokeWidth={1.8} />
        </span>
      </div>
      <p className="mt-4 break-words text-2xl font-semibold tracking-[-0.04em] text-ink sm:text-[1.7rem]">{value}</p>
      <p className="mt-1 text-xs leading-5 text-ink-muted">{subtitle}</p>
    </>
  )
  const classes = `relative min-w-0 overflow-hidden rounded-xl border bg-surface p-4 shadow-sm transition-colors sm:p-5 ${tone === 'attention' ? 'border-amber-500/35' : 'border-line'} ${to ? 'hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent' : ''}`
  return to ? <Link className={classes} to={to}>{content}<ArrowUpRight aria-hidden="true" className="absolute bottom-4 right-4 size-3.5 text-ink-muted" /></Link> : <article className={classes}>{content}</article>
}

export function HighlightCard({ title, value, detail, to, icon }: { title: string; value: string; detail: string; to?: string; icon?: ReactNode }) {
  const content = (
    <>
      <div className="flex items-center justify-between gap-3">
        <p className="text-[0.65rem] font-semibold uppercase tracking-[0.13em] text-ink-muted">{title}</p>
        {icon}
      </div>
      <p className="mt-3 truncate text-sm font-semibold text-ink">{value}</p>
      <p className="mt-1 text-xs text-ink-muted">{detail}</p>
    </>
  )
  const classes = `min-w-0 rounded-lg border border-line bg-surface-raised p-4 ${to ? 'transition-colors hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent' : ''}`
  return to ? <Link className={classes} to={to}>{content}</Link> : <article className={classes}>{content}</article>
}
