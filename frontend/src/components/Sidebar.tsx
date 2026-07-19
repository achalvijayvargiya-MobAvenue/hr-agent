import React, { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Briefcase, Users, Star, Settings, ChevronLeft, ChevronRight } from 'lucide-react'
import { useCurrentUser } from '../modules/auth/useAuth'

interface NavItem {
  to: string
  label: string
  adminOnly?: boolean
  icon: React.ElementType
}

const navItems: NavItem[] = [
  { to: '/positions', label: 'Positions', icon: Briefcase },
  { to: '/candidates', label: 'Candidates', icon: Users },
  { to: '/matches', label: 'Matches', icon: Star },
  { to: '/users', label: 'Users', adminOnly: true, icon: Settings },
]

export default function Sidebar() {
  const { data: user } = useCurrentUser()
  const isAdmin = user?.roles?.includes('admin') ?? false
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <aside 
      className={`flex flex-col min-h-screen bg-zinc-900 border-r border-zinc-800 animate-fade-in shrink-0 z-20 transition-all duration-300 relative ${isExpanded ? 'w-56' : 'w-20'}`}
    >
      {/* Toggle Button */}
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="absolute -right-3 top-6 bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-zinc-100 rounded-full p-1 z-30 transition-colors"
      >
        {isExpanded ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
      </button>

      <div className="flex h-16 items-center justify-center border-b border-zinc-800/50 overflow-hidden px-2">
        <div className="w-8 h-8 rounded flex items-center justify-center shrink-0">
          <img src="/logo-removebg-preview.png" alt="Logo" className="w-full h-full object-contain" />
        </div>
        {isExpanded && <span className="ml-2 font-semibold text-zinc-100 tracking-wide truncate">Mobavenue</span>}
      </div>

      <nav className="flex-1 py-4 flex flex-col items-center space-y-2 px-2 overflow-hidden">
        {navItems.map((item, idx) => {
          if (item.adminOnly && !isAdmin) return null
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center w-full rounded-xl transition-all duration-200 group relative ${
                  isExpanded ? 'h-12 px-3' : 'h-16 justify-center flex-col'
                } ${
                  isActive
                    ? 'text-orange-400 bg-zinc-800 shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50'
                } animate-fade-in`
              }
              style={{ animationDelay: `${idx * 50}ms` }}
            >
              {({ isActive }) => (
                <>
                  <div className={`transition-transform duration-200 ${isExpanded ? 'mr-3' : 'mb-1'} ${isActive ? 'scale-110' : 'group-hover:scale-110'}`}>
                    <Icon size={20} />
                  </div>
                  <span className={`font-medium tracking-tight truncate ${isExpanded ? 'text-sm' : 'text-[10px] w-full text-center px-1'}`}>
                    {item.label}
                  </span>
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-orange-500 rounded-r-md shadow-[0_0_8px_rgba(249,115,22,0.4)]" />
                  )}
                </>
              )}
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}

