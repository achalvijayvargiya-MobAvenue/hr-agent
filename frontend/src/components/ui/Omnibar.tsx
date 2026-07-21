import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Briefcase, User, X } from 'lucide-react'
import { usePositions } from '../../modules/positions/hooks/usePositions'
import { useCandidates } from '../../modules/candidates/hooks/useSources'

export function Omnibar() {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  
  const { data: positions = [] } = usePositions()
  const { data: paginatedData } = useCandidates(undefined, undefined, undefined, query)
  const candidates = paginatedData?.items || []
  
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setIsOpen((open) => !open)
      }
      if (e.key === 'Escape') {
        setIsOpen(false)
      }
    }
    const openOmnibar = () => setIsOpen(true)

    document.addEventListener('keydown', down)
    window.addEventListener('open-omnibar', openOmnibar)
    return () => {
      document.removeEventListener('keydown', down)
      window.removeEventListener('open-omnibar', openOmnibar)
    }
  }, [])

  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  const filteredPositions = positions
    .filter((p) => p.title?.toLowerCase().includes(query.toLowerCase()) || p.id.toLowerCase().includes(query.toLowerCase()))
    .slice(0, 5)

  const filteredCandidates = candidates.slice(0, 5)

  const allResults = [
    ...filteredPositions.map(p => ({ type: 'position', data: p })),
    ...filteredCandidates.map(c => ({ type: 'candidate', data: c }))
  ]

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev < allResults.length - 1 ? prev + 1 : prev))
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev))
    }
    if (e.key === 'Enter' && allResults[selectedIndex]) {
      e.preventDefault()
      const item = allResults[selectedIndex]
      if (item.type === 'position') {
        navigate(`/positions/${(item.data as any).id}`)
      } else {
        navigate(`/candidates/${encodeURIComponent((item.data as any).email)}`)
      }
      setIsOpen(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] sm:pt-[20vh] px-4 animate-fade-in bg-zinc-950/80 backdrop-blur-sm">
      <div 
        className="fixed inset-0"
        onClick={() => setIsOpen(false)}
      />
      <div className="relative w-full max-w-2xl bg-zinc-900 border border-zinc-700 shadow-2xl rounded-xl overflow-hidden flex flex-col animate-slide-up">
        <div className="flex items-center px-4 py-3 border-b border-zinc-800">
          <Search size={18} className="text-zinc-500 mr-3" />
          <input
            ref={inputRef}
            className="flex-1 bg-transparent border-none text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-0 text-base"
            placeholder="Search positions or candidates..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button 
            onClick={() => setIsOpen(false)}
            className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <div className="max-h-[60vh] overflow-y-auto custom-scrollbar">
          {query.trim() === '' ? (
            <div className="p-8 text-center text-sm text-zinc-500">
              Start typing to search across your workspace...
            </div>
          ) : allResults.length === 0 ? (
            <div className="p-8 text-center text-sm text-zinc-500">
              No results found for "{query}"
            </div>
          ) : (
            <div className="py-2">
              {filteredPositions.length > 0 && (
                <div className="px-4 py-1 mt-2 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                  Positions
                </div>
              )}
              {filteredPositions.map((p, idx) => {
                const isSelected = selectedIndex === idx
                return (
                  <div
                    key={p.id}
                    onClick={() => {
                      navigate(`/positions/${p.id}`)
                      setIsOpen(false)
                    }}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
                      isSelected ? 'bg-orange-500/10 border-l-2 border-orange-500' : 'border-l-2 border-transparent hover:bg-zinc-800/50'
                    }`}
                  >
                    <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-zinc-800 text-orange-400">
                      <Briefcase size={14} />
                    </div>
                    <div>
                      <div className={`text-sm font-medium ${isSelected ? 'text-orange-400' : 'text-zinc-200'}`}>
                        {p.title || p.id}
                      </div>
                      <div className="text-xs text-zinc-500">
                        {p.status} • {p.department || 'No department'}
                      </div>
                    </div>
                  </div>
                )
              })}

              {filteredCandidates.length > 0 && (
                <div className="px-4 py-1 mt-2 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                  Candidates
                </div>
              )}
              {filteredCandidates.map((c, idx) => {
                const globalIdx = filteredPositions.length + idx
                const isSelected = selectedIndex === globalIdx
                return (
                  <div
                    key={c.email}
                    onClick={() => {
                      navigate(`/candidates/${encodeURIComponent(c.email)}`)
                      setIsOpen(false)
                    }}
                    onMouseEnter={() => setSelectedIndex(globalIdx)}
                    className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
                      isSelected ? 'bg-blue-500/10 border-l-2 border-blue-500' : 'border-l-2 border-transparent hover:bg-zinc-800/50'
                    }`}
                  >
                    <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-zinc-800 text-blue-400">
                      <User size={14} />
                    </div>
                    <div>
                      <div className={`text-sm font-medium ${isSelected ? 'text-blue-400' : 'text-zinc-200'}`}>
                        {c.name || c.email}
                      </div>
                      <div className="text-xs text-zinc-500">
                        {c.current_title || 'No title'} • {c.email}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
        <div className="px-4 py-2 border-t border-zinc-800 bg-zinc-900/50 flex items-center justify-between text-xs text-zinc-500">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 font-sans bg-zinc-800 rounded text-zinc-400 text-[10px]">↑↓</kbd> to navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 font-sans bg-zinc-800 rounded text-zinc-400 text-[10px]">Enter</kbd> to select
            </span>
          </div>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 font-sans bg-zinc-800 rounded text-zinc-400 text-[10px]">Esc</kbd> to close
          </span>
        </div>
      </div>
    </div>
  )
}
