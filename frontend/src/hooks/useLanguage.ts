import { useTranslation } from 'react-i18next'

import type { AppLanguage } from '../i18n'

export function useLanguage() {
  const { i18n } = useTranslation()
  return { language: i18n.language as AppLanguage, setLanguage: (language: AppLanguage) => void i18n.changeLanguage(language) }
}
