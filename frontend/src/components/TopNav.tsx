import { useState, useRef, useEffect } from 'react'
import { useLocation, Link } from 'react-router-dom'
import { LogOut, Search, ChevronRight } from 'lucide-react'
import { useCurrentUser, useLogout } from '../modules/auth/useAuth'

export default function TopNav() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const location = useLocation()

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Generate basic breadcrumbs
  const pathnames = location.pathname.split('/').filter((x) => x)

  return (
    <header className="flex items-center justify-between h-14 bg-zinc-900 border-b border-zinc-800 px-4 text-zinc-300 animate-fade-in shrink-0 z-20 shadow-sm relative">
      <div className="flex items-center gap-6 h-full flex-1">
        <div className="flex items-center gap-2 pr-6 border-r border-zinc-800 h-full">
          <Link to="/">
            <img src="/logo-removebg-preview.png" alt="Mobavenue" className="h-8 object-contain" />
          </Link>
        </div>

        {/* Breadcrumbs */}
        <nav className="hidden md:flex items-center text-sm font-medium text-zinc-400">
          <Link to="/" className="hover:text-zinc-100 transition-colors">Home</Link>
          {pathnames.map((name, index) => {
            const routeTo = `/${pathnames.slice(0, index + 1).join('/')}`
            const isLast = index === pathnames.length - 1
            return (
              <div key={name} className="flex items-center">
                <ChevronRight size={14} className="mx-2 text-zinc-600" />
                {isLast ? (
                  <span className="text-zinc-100 capitalize">{name.replace(/-/g, ' ')}</span>
                ) : (
                  <Link to={routeTo} className="hover:text-zinc-100 transition-colors capitalize">
                    {name.replace(/-/g, ' ')}
                  </Link>
                )}
              </div>
            )
          })}
        </nav>
      </div>

      {/* Centered Search */}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden md:block">
        <button 
          onClick={() => window.dispatchEvent(new Event('open-omnibar'))}
          className="flex items-center justify-between w-[320px] px-3 py-1.5 text-sm text-zinc-400 bg-zinc-950 border border-zinc-700/50 rounded-md hover:border-zinc-600 hover:text-zinc-300 transition-colors shadow-inner"
        >
          <div className="flex items-center gap-2">
            <Search size={14} />
            <span>Search...</span>
          </div>
          <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-sans bg-zinc-800 border border-zinc-700 rounded text-zinc-400">
            Cmd+K
          </kbd>
        </button>
      </div>

      <div className="flex items-center gap-4 relative flex-1 justify-end" ref={menuRef}>

        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center justify-center w-9 h-9 rounded-full bg-gradient-to-tr from-orange-600 to-orange-800 border border-zinc-700 text-white text-xs font-bold shadow-inner uppercase hover:ring-2 hover:ring-orange-500 hover:ring-offset-2 hover:ring-offset-zinc-900 transition-all focus:outline-none"
        >
          {user?.email?.substring(0, 2) || 'VK'}
        </button>

        {/* Dropdown Menu */}
        <div
          className={`absolute right-0 top-12 w-48 rounded-lg bg-zinc-900 border border-zinc-700/50 shadow-xl overflow-hidden transition-all duration-200 origin-top-right transform ${
            isOpen ? 'scale-100 opacity-100 visible' : 'scale-95 opacity-0 invisible'
          }`}
        >
          <div className="px-4 py-3 border-b border-zinc-800/50 bg-zinc-900/50">
            <p className="text-sm font-medium text-zinc-100 truncate">{user?.full_name || 'User'}</p>
            <p className="text-xs text-zinc-400 truncate mt-0.5">{user?.email}</p>
          </div>
          <div className="p-1">
            <button
              onClick={() => {
                setIsOpen(false)
                logout()
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-400 rounded-md hover:bg-zinc-800/50 hover:text-red-300 transition-colors group"
            >
              <LogOut size={16} className="transition-transform group-hover:-translate-x-1" />
              Sign out
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
