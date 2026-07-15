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
          <div className="w-8 h-8 bg-gradient-to-tr from-indigo-600 to-indigo-800 rounded-md flex items-center justify-center text-white font-bold text-lg shadow-sm">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
              <path d="M4.5 6.375a4.125 4.125 0 118.25 0 4.125 4.125 0 01-8.25 0zM14.25 8.625a3.375 3.375 0 116.75 0 3.375 3.375 0 01-6.75 0zM1.5 19.125a7.125 7.125 0 0114.25 0v.003l-.001.119a.75.75 0 01-.363.63 13.067 13.067 0 01-6.761 1.873c-2.472 0-4.786-.684-6.76-1.873a.75.75 0 01-.364-.63l-.001-.122zM17.25 19.128l-.001.144a2.25 2.25 0 01-.233.96 10.088 10.088 0 005.06-1.01.75.75 0 00.42-.643 4.875 4.875 0 00-6.957-4.611 8.586 8.586 0 011.71 5.157v.003z" />
            </svg>
          </div>
          <span className="font-bold text-zinc-100 tracking-tight text-lg">HR Platform</span>
        </div>
      </div>

      <div className="flex items-center gap-4 relative" ref={menuRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center justify-center w-9 h-9 rounded-full bg-gradient-to-tr from-indigo-600 to-indigo-800 border border-zinc-700 text-white text-xs font-bold shadow-inner uppercase hover:ring-2 hover:ring-indigo-500 hover:ring-offset-2 hover:ring-offset-zinc-900 transition-all focus:outline-none"
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
