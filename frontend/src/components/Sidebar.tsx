import { NavLink } from 'react-router-dom'
import { useCurrentUser, useLogout } from '../modules/auth/useAuth'

interface NavItem {
  to: string
  label: string
  adminOnly?: boolean
}

const navItems: NavItem[] = [
  { to: '/positions', label: 'Positions' },
  { to: '/candidates', label: 'Candidates' },
  { to: '/sources', label: 'Sources' },
  { to: '/matches', label: 'Matches' },
  { to: '/users', label: 'Users', adminOnly: true },
]

export default function Sidebar() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const isAdmin = user?.roles?.includes('admin') ?? false

  return (
    <aside className="flex flex-col w-56 min-h-screen bg-white border-r border-gray-200">
      <div className="px-6 py-5 border-b border-gray-100">
        <span className="text-lg font-bold text-indigo-600">HR Platform</span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          if (item.adminOnly && !isAdmin) return null
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-600'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              {item.label}
            </NavLink>
          )
        })}
      </nav>

      <div className="px-4 py-4 border-t border-gray-100">
        {user && (
          <p className="text-xs text-gray-500 truncate mb-2" title={user.email}>
            {user.email}
          </p>
        )}
        <button
          onClick={logout}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-colors"
        >
          Logout
        </button>
      </div>
    </aside>
  )
}
