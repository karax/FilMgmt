import { useTranslation } from 'react-i18next'

export function AnalyticsSkeleton() {
  const { t } = useTranslation()
  return (
    <div aria-label={t('analytics.loading')} className="animate-pulse" role="status">
      <span className="sr-only">{t('analytics.loading')}</span>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => <div className="h-36 rounded-xl border border-line bg-surface" key={index} />)}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <div className="h-80 rounded-xl border border-line bg-surface" />
        <div className="h-80 rounded-xl border border-line bg-surface" />
      </div>
      <div className="mt-6 h-80 rounded-xl border border-line bg-surface" />
    </div>
  )
}
