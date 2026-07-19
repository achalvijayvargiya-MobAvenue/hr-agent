import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

interface DrawerProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  size?: 'md' | 'lg' | 'xl'
}

export function Drawer({ isOpen, onClose, title, children, size = 'md' }: DrawerProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    if (isOpen) {
      document.body.style.overflow = 'hidden'
      document.addEventListener('keydown', handleKeyDown)
    }
    return () => {
      document.body.style.overflow = 'unset'
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, onClose])

  const sizeClasses = {
    md: 'w-full max-w-md',
    lg: 'w-full max-w-2xl',
    xl: 'w-full max-w-4xl',
  }

  return (
    <>
      {/* Backdrop */}
      <div
        ref={overlayRef}
        onClick={(e) => e.target === overlayRef.current && onClose()}
        className={`fixed inset-0 z-40 bg-zinc-950/80 backdrop-blur-sm transition-opacity duration-300 ${
          isOpen ? 'opacity-100 visible' : 'opacity-0 invisible'
        }`}
      />

      {/* Drawer Panel */}
      <div
        className={`fixed inset-y-0 right-0 z-50 flex flex-col bg-zinc-950 border-l border-zinc-800 shadow-2xl transition-transform duration-300 ease-in-out transform ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        } ${sizeClasses[size]}`}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-900/50">
          <h2 className="text-lg font-semibold text-zinc-100 truncate">{title}</h2>
          <button
            onClick={onClose}
            className="p-2 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-full transition-colors focus:outline-none"
          >
            <X size={20} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
          {children}
        </div>
      </div>
    </>
  )
}
