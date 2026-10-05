import { BookOpen, ChevronRight, Download, Tags } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { LanguageSelector } from '../components/settings/LanguageSelector'
import manual from '../config/manual.json'

export function SettingsPage() {
  const { t } = useTranslation()
  return (
    <section aria-labelledby="settings-title" className="max-w-3xl">
      <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">FCC / 06</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] text-ink" id="settings-title">{t('settings.title')}</h2>
      <p className="mt-3 text-base leading-7 text-ink-muted">{t('settings.description')}</p>

      <section aria-labelledby="language-title" className="mt-8 rounded-lg border border-line bg-surface p-5 shadow-sm">
        <h3 className="text-lg font-semibold text-ink" id="language-title">{t('settings.language')}</h3>
        <p className="mt-1 text-sm text-ink-muted">{t('settings.languageDescription')}</p>
        <div className="mt-5"><LanguageSelector /></div>
      </section>

      <a className="mt-6 flex items-center gap-3 rounded-lg border border-line bg-surface p-5 shadow-sm transition-colors hover:bg-surface-raised" href="/settings/catalogs">
        <span aria-hidden="true" className="rounded-md bg-accent-soft p-2 text-accent"><Tags className="size-5" /></span>
        <span className="min-w-0 flex-1">
          <span className="block text-lg font-semibold text-ink">{t('catalogs.title')}</span>
          <span className="mt-1 block text-sm leading-6 text-ink-muted">{t('catalogs.settingsDescription')}</span>
        </span>
        <ChevronRight aria-hidden="true" className="size-5 shrink-0 text-ink-muted" />
      </a>

      <section aria-labelledby="manual-title" className="mt-6 rounded-lg border border-line bg-surface p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <span aria-hidden="true" className="mt-0.5 rounded-md bg-accent-soft p-2 text-accent">
            <BookOpen className="size-5" />
          </span>
          <div>
            <h3 className="text-lg font-semibold text-ink" id="manual-title">{t('settings.manual.title')}</h3>
            <p className="mt-1 text-sm leading-6 text-ink-muted">{t('settings.manual.description')}</p>
          </div>
        </div>
        <a
          className="mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:w-auto"
          download={manual.filename}
          href={manual.url}
        >
          <Download aria-hidden="true" className="size-4" />
          {t('settings.manual.download')}
        </a>
      </section>
    </section>
  )
}
