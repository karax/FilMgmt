import type { LucideIcon } from 'lucide-react'
import {
  ChartNoAxesCombined,
  LayoutDashboard,
  Lightbulb,
  PackageOpen,
  Printer,
  Settings2,
} from 'lucide-react'

export interface NavigationItem {
  labelKey: string
  path: string
  icon: LucideIcon
}

export const navigationItems: readonly NavigationItem[] = [
  { labelKey: 'navigation.dashboard', path: '/', icon: LayoutDashboard },
  { labelKey: 'navigation.inventory', path: '/inventory', icon: PackageOpen },
  { labelKey: 'navigation.prints', path: '/prints', icon: Printer },
  { labelKey: 'navigation.advisor', path: '/advisor', icon: Lightbulb },
  {
    labelKey: 'navigation.analytics',
    path: '/analytics',
    icon: ChartNoAxesCombined,
  },
  { labelKey: 'navigation.settings', path: '/settings', icon: Settings2 },
]

export function getPageTitleKey(pathname: string): string {
  if (pathname === '/inventory/new') return 'spool.new'
  if (pathname === '/prints/new') return 'prints.actions.new'
  if (pathname.startsWith('/prints/') && pathname.endsWith('/edit')) return 'prints.actions.edit'
  if (pathname.endsWith('/edit')) return 'spool.edit'

  return navigationItems.find((item) => item.path === pathname)?.labelKey ?? 'common.appName'
}
