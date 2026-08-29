import { NavLink } from 'react-router-dom'

import { navigationItems } from '../../navigation'

export function NavigationList() {
  return (
    <ul className="space-y-1" role="list">
      {navigationItems.map(({ icon: Icon, label, path }) => (
        <li key={path}>
          <NavLink
            className={({ isActive }) =>
              [
                'group relative flex min-h-11 items-center gap-3 rounded-md border px-3 py-2.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent',
                isActive
                  ? 'border-white/10 bg-white/10 font-semibold text-white shadow-[inset_3px_0_0_var(--accent)]'
                  : 'border-transparent text-sidebar-muted hover:bg-white/5 hover:text-white',
              ].join(' ')
            }
            end={path === '/'}
            to={path}
          >
            <Icon
              aria-hidden="true"
              className="size-[1.1rem] shrink-0"
              strokeWidth={1.8}
            />
            <span>{label}</span>
          </NavLink>
        </li>
      ))}
    </ul>
  )
}
