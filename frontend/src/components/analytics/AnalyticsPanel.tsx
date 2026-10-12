import { AlertCircle, BarChart3 } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

interface AnalyticsPanelProps {
  title: string
  subtitle?: string
  children?: ReactNode
  isLoading?: boolean
  error?: unknown
  isEmpty?: boolean
  emptyMessage?: string
  onRetry?: () => void
  className?: string
  action?: ReactNode
}

export function AnalyticsPanel({
  title,
  subtitle,
  children,
  isLoading = false,
  error,
  isEmpty = false,
  emptyMessage,
  onRetry,
  className = '',
  action,
}: AnalyticsPanelProps) {
  const { t } = useTranslation()

  return (
    <section className={`min-w-0 rounded-xl border border-line bg-surface p-4 shadow-sm sm:p-5 ${className}`}>
      <div className="flex min-h-12 items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold tracking-[-0.015em] text-ink">{title}</h3>
          {subtitle && <p className="mt-1 text-xs leading-5 text-ink-muted">{subtitle}</p>}
        </div>
        {action}
      </div>
      {isLoading ? (
        <div aria-label={t('analytics.loadingChart', { title })} className="mt-4 h-64 animate-pulse rounded-lg bg-canvas" role="status">
          <span className="sr-only">{t('analytics.loadingChart', { title })}</span>
        </div>
      ) : error ? (
        <div className="mt-5 grid min-h-56 place-items-center rounded-lg border border-dashed border-red-500/30 bg-red-500/[0.03] px-4 text-center" role="alert">
          <div>
            <AlertCircle aria-hidden="true" className="mx-auto size-5 text-red-600 dark:text-red-400" />
            <p className="mt-2 text-sm font-semibold text-ink">{t('analytics.chartUnavailable')}</p>
            {onRetry && (
              <button className="mt-3 rounded-md border border-line bg-surface-raised px-3 py-2 text-xs font-semibold text-ink hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" onClick={onRetry} type="button">
                {t('common.retry')}
              </button>
            )}
          </div>
        </div>
      ) : isEmpty ? (
        <div className="mt-5 grid min-h-56 place-items-center rounded-lg border border-dashed border-line bg-canvas/50 px-5 text-center">
          <div>
            <BarChart3 aria-hidden="true" className="mx-auto size-5 text-ink-muted" />
            <p className="mt-2 text-sm text-ink-muted">{emptyMessage}</p>
          </div>
        </div>
      ) : (
        <div className="mt-4">{children}</div>
      )}
    </section>
  )
}
