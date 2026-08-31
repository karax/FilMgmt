import { PagePlaceholder } from '../components/layout/PagePlaceholder'
import { useTranslation } from 'react-i18next'

export function AdvisorPage() {
  const { t } = useTranslation()
  return (
    <PagePlaceholder
      description={t('placeholders.advisorDescription')}
      moduleCode="04"
      title={t('placeholders.advisorTitle')}
    />
  )
}
