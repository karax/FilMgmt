function SkeletonCard() {
  return (
    <div
      aria-hidden="true"
      className="h-36 animate-pulse rounded-lg border border-line bg-surface"
    >
      <div className="p-5">
        <div className="h-3 w-24 rounded bg-line" />
        <div className="mt-7 h-7 w-20 rounded bg-line" />
        <div className="mt-3 h-3 w-28 rounded bg-line" />
      </div>
    </div>
  )
}

export function DashboardSkeleton() {
  const { t } = useTranslation()
  return (
    <div aria-busy="true" aria-label={t('dashboard.loading')} role="status">
      <span className="sr-only">{t('dashboard.loading')}</span>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:gap-4 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, index) => (
          <SkeletonCard key={index} />
        ))}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(18rem,0.75fr)_minmax(0,1.25fr)]">
        <div className="h-72 animate-pulse rounded-lg border border-line bg-surface" />
        <div className="h-72 animate-pulse rounded-lg border border-line bg-surface" />
      </div>
    </div>
  )
}
import { useTranslation } from 'react-i18next'
