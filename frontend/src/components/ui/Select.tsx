import { useState, useRef, useEffect } from 'react'

export interface SelectOption {
  label: string
  value: string
}

export interface SelectProps {
  value: string | number
  onChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  className?: string
  disabled?: boolean
}

export function Select({ value, onChange, options, placeholder = 'Select...', className = '', disabled = false }: SelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const selectedOption = options.find((opt) => String(opt.value) === String(value))

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className={`relative ${className}`} ref={containerRef}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between gap-2 bg-transparent text-base font-semibold focus:outline-none focus:ring-0 cursor-pointer p-0 m-0 text-left disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <span className={selectedOption ? 'text-white' : 'text-zinc-500'}>
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`w-5 h-5 text-zinc-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}>
          <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
        </svg>
      </button>

      {/* Dropdown Menu */}
      <div className={`absolute top-[calc(100%+12px)] left-0 w-full min-w-[240px] z-[100] bg-zinc-900/95 backdrop-blur-xl border border-zinc-700 rounded-xl shadow-2xl p-2 transition-all transform origin-top-left ${isOpen ? 'opacity-100 scale-100' : 'opacity-0 scale-95 pointer-events-none'}`}>
        <div className="space-y-1 max-h-[300px] overflow-y-auto custom-scrollbar">
          {options.length === 0 ? (
            <div className="p-2.5 text-sm text-zinc-500 text-center">No options available</div>
          ) : (
            options.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  onChange(opt.value)
                  setIsOpen(false)
                }}
                className={`w-full text-left p-2.5 rounded-lg cursor-pointer transition-colors text-sm font-medium ${String(value) === String(opt.value) ? 'bg-orange-500/20 text-orange-400' : 'text-zinc-200 hover:bg-zinc-800/80'}`}
              >
                {opt.label}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
