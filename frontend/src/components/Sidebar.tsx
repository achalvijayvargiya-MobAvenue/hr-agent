import React from 'react'
import { NavLink } from 'react-router-dom'
import { useCurrentUser } from '../modules/auth/useAuth'

interface NavItem {
  to: string
  label: string
  adminOnly?: boolean
  icon: React.ReactNode
}

function getIcon(name: string) {
  switch (name) {
    case 'Positions':
      return (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" />
        </svg>
      )
    case 'Candidates':
      return (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
        </svg>
      )
    case 'Sources':
      return (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
        </svg>
      )
    case 'Matches':
      return (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
          <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-1.81.588l1.234 5.397c.113.495-.413.883-.842.618l-4.634-2.859a.562.562 0 00-.585 0l-4.634 2.859c-.43.265-.955-.123-.842-.618l1.234-5.397a.563.563 0 00-1.81-.588l-4.204-3.602c-.38-.325-.178-.948.321-.988l5.518-.442a.563.563 0 00.475-.345l2.125-5.111z" />
        </svg>
      )
    case 'Users':
      return (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 110-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38c-.551.318-1.26.117-1.527-.461a20.845 20.845 0 01-1.44-4.282m3.102.069a18.03 18.03 0 013.627 0m0 0c.34.05.68.114 1.02.193m-1.02-.193L13 16.5m0 0l-1.43 1.43m1.43-1.43L15 18m-2-1.5V21" />
        </svg>
      )
    default:
      return <div />
  }
}

const navItems: NavItem[] = [
  { to: '/positions', label: 'Positions', icon: getIcon('Positions') },
  { to: '/candidates', label: 'Candidates', icon: getIcon('Candidates') },
  { to: '/sources', label: 'Sources', icon: getIcon('Sources') },
  { to: '/matches', label: 'Matches', icon: getIcon('Matches') },
  { to: '/users', label: 'Users', adminOnly: true, icon: getIcon('Users') },
]

export default function Sidebar() {
  const { data: user } = useCurrentUser()
  const isAdmin = user?.roles?.includes('admin') ?? false

  return (
    <aside className="flex flex-col w-20 min-h-screen bg-zinc-900 border-r border-zinc-800 animate-fade-in shrink-0 z-10">
      <nav className="flex-1 py-4 flex flex-col items-center space-y-2">
        {navItems.map((item, idx) => {
          if (item.adminOnly && !isAdmin) return null
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center w-16 h-16 rounded-xl transition-all duration-200 group relative ${
                  isActive
                    ? 'text-indigo-400 bg-zinc-800 shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50'
                } animate-fade-in`
              }
              style={{ animationDelay: `${idx * 50}ms` }}
            >
              {({ isActive }) => (
                <>
                  <div className={`mb-1 transition-transform duration-200 ${isActive ? 'scale-110' : 'group-hover:scale-110'}`}>
                    {item.icon}
                  </div>
                  <span className="text-[10px] font-medium tracking-tight truncate w-full text-center px-1">
                    {item.label}
                  </span>
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-indigo-500 rounded-r-md shadow-[0_0_8px_rgba(99,102,241,0.6)]" />
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
