import { PagePlaceholder } from '../components/layout/PagePlaceholder'
import { useTranslation } from 'react-i18next'

export function AnalyticsPage() {
  const { t } = useTranslation()
  return (
    <PagePlaceholder
      description={t('placeholders.analyticsDescription')}
      moduleCode="05"
      title={t('placeholders.analyticsTitle')}
    />
  )
}
