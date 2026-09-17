import { Brand } from './Brand'
import { NavigationList } from './NavigationList'
import { useTranslation } from 'react-i18next'

export function Sidebar() {
  const { t } = useTranslation()
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 border-r border-white/8 bg-sidebar lg:flex lg:flex-col">
      <div className="border-b border-white/8 px-6 py-5">
        <Brand />
      </div>
      <nav aria-label={t('navigation.openNavigation')} className="flex-1 px-4 py-6">
        <NavigationList />
      </nav>
      <div className="mx-4 mb-5 border-t border-white/8 pt-4">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-sidebar-muted">
          FCC / {t('common.operationsShell')}
        </p>
      </div>
    </aside>
  )
}
