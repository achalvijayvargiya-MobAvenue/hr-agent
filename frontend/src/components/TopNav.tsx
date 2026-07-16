import { useState, useRef, useEffect } from 'react'
import { useCurrentUser, useLogout } from '../modules/auth/useAuth'

export default function TopNav() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <header className="flex items-center justify-between h-14 bg-zinc-900 border-b border-zinc-800 px-4 text-zinc-300 animate-fade-in shrink-0 z-20 shadow-sm relative">
      <div className="flex items-center gap-6 h-full">
        <div className="flex items-center gap-2 pr-6 border-r border-zinc-800 h-full">
          <img src="/logo.png" alt="Logo" className="h-12 w-auto" />
        </div>
      </div>

      <div className="flex items-center gap-4 relative" ref={menuRef}>
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
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 transition-transform group-hover:scale-110">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
              </svg>
              Sign out
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
