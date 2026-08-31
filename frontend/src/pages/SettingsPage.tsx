import { useTranslation } from 'react-i18next'

import { LanguageSelector } from '../components/settings/LanguageSelector'

export function SettingsPage() {
  const { t } = useTranslation()
  return <section aria-labelledby="settings-title" className="max-w-3xl"><p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">FCC / 06</p><h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] text-ink" id="settings-title">{t('settings.title')}</h2><p className="mt-3 text-base leading-7 text-ink-muted">{t('settings.description')}</p><section aria-labelledby="language-title" className="mt-8 rounded-lg border border-line bg-surface p-5 shadow-sm"><h3 className="text-lg font-semibold text-ink" id="language-title">{t('settings.language')}</h3><p className="mt-1 text-sm text-ink-muted">{t('settings.languageDescription')}</p><div className="mt-5"><LanguageSelector /></div></section></section>
}
