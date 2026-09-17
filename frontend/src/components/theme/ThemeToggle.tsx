import { MonitorCog, Moon, Sun } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { type Theme, useTheme } from './ThemeProvider'

const themeIcons = {
  light: Sun,
  dark: Moon,
  system: MonitorCog,
} satisfies Record<Theme, typeof Sun>

export function ThemeToggle() {
  const { t } = useTranslation()
  const { theme, setTheme } = useTheme()
  const ThemeIcon = themeIcons[theme]

  return (
    <label className="relative flex items-center gap-2 rounded-md border border-line bg-surface-raised px-2.5 py-2 text-ink-muted transition-colors hover:border-accent hover:text-ink focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent">
      <ThemeIcon aria-hidden="true" className="size-4" strokeWidth={1.8} />
      <span className="sr-only">{t('theme.preference')}</span>
      <select
        aria-label={t('theme.preference')}
        className="cursor-pointer appearance-none bg-transparent pr-4 text-xs font-semibold uppercase tracking-[0.12em] outline-none"
        value={theme}
        onChange={(event) => setTheme(event.target.value as Theme)}
      >
        <option value="system">{t('theme.system')}</option>
        <option value="light">{t('theme.light')}</option>
        <option value="dark">{t('theme.dark')}</option>
      </select>
      <span
        aria-hidden="true"
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[0.55rem]"
      >
        ▾
      </span>
    </label>
  )
}
