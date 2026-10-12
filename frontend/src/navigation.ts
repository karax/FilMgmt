import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  BarChart3,
  ClipboardCheck,
  FileCode2,
  LayoutDashboard,
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
  { labelKey: 'navigation.inventory', path: '/inventory', icon: PackageOpen },
  { labelKey: 'navigation.dashboard', path: '/dashboard', icon: LayoutDashboard },
  { labelKey: 'navigation.printerStatus', path: '/printer-status', icon: Activity },
  { labelKey: 'navigation.reconciliation', path: '/reconciliation', icon: ClipboardCheck },
  { labelKey: 'navigation.prints', path: '/prints', icon: Printer },
  { labelKey: 'navigation.analytics', path: '/analytics', icon: BarChart3 },
  { labelKey: 'navigation.gcode', path: '/gcode', icon: FileCode2 },
  { labelKey: 'navigation.settings', path: '/settings', icon: Settings2 },
]

export function getPageTitleKey(pathname: string): string {
  if (pathname === '/analytics') return 'navigation.analytics'
  if (pathname === '/settings/catalogs') return 'catalogs.title'
  if (pathname === '/inventory/new') return 'spool.new'
  if (pathname === '/scan') return 'scan.pageTitle'
  if (pathname.startsWith('/qr/spool/')) return 'qr.spool.pageTitle'
  if (pathname === '/prints/new') return 'prints.actions.new'
  if (pathname === '/reconciliation') return 'navigation.reconciliation'
  if (pathname.startsWith('/prints/') && pathname.endsWith('/edit')) return 'prints.actions.edit'
  if (pathname.endsWith('/edit')) return 'spool.edit'

  return navigationItems.find((item) => item.path === pathname)?.labelKey ?? 'common.appName'
}
