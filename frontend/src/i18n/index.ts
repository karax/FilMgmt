import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { en } from './locales/en'
import { ptBR } from './locales/pt-BR'

export const LANGUAGE_STORAGE_KEY = 'fcc-language'
export const supportedLanguages = ['pt-BR', 'en'] as const
export type AppLanguage = (typeof supportedLanguages)[number]

export function resolveStoredLanguage(stored: string | null): AppLanguage {
  return stored === 'en' || stored === 'pt-BR' ? stored : 'pt-BR'
}

function initialLanguage(): AppLanguage {
  const stored = typeof window === 'undefined' ? null : window.localStorage.getItem(LANGUAGE_STORAGE_KEY)
  return resolveStoredLanguage(stored)
}

function applyDocumentLanguage(language: string): void {
  if (typeof document !== 'undefined') document.documentElement.lang = language === 'en' ? 'en' : 'pt-BR'
}

const language = initialLanguage()
applyDocumentLanguage(language)

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, 'pt-BR': { translation: ptBR } },
  lng: language, fallbackLng: 'en', interpolation: { escapeValue: false },
})

i18n.on('languageChanged', (language) => {
  if (language === 'en' || language === 'pt-BR') {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
    applyDocumentLanguage(language)
  }
})

export default i18n
