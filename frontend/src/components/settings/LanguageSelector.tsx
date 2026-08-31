import { useTranslation } from 'react-i18next'

import { useLanguage } from '../../hooks/useLanguage'

export function LanguageSelector() {
  const { t } = useTranslation()
  const { language, setLanguage } = useLanguage()
  return <label className="block text-sm font-semibold text-ink">{t('settings.language')}<select className="mt-2 w-full max-w-sm rounded-md border border-line bg-surface px-3 py-2.5 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent/20" onChange={(event) => setLanguage(event.target.value as 'pt-BR' | 'en')} value={language}><option value="pt-BR">{t('settings.portuguese')}</option><option value="en">{t('settings.english')}</option></select></label>
}
