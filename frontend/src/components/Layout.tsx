import Sidebar from './Sidebar'
import TopNav from './TopNav'
import { Omnibar } from './ui/Omnibar'

interface Props {
  children: React.ReactNode
}

export default function Layout({ children }: Props) {
  return (
    <div className="flex flex-col min-h-screen bg-zinc-950 font-sans text-zinc-100 overflow-hidden">
      <TopNav />
      <div className="flex flex-1 overflow-hidden relative">
        {/* Subtle abstract background gradient */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-orange-900/20 via-zinc-950 to-zinc-950 z-0 pointer-events-none" />
        
        <Sidebar />
        
        <main className="flex-1 overflow-y-auto z-10">
          <div className="max-w-[1600px] mx-auto p-6 md:p-8 min-h-full">
            {children}
          </div>
        </main>
      </div>
      <Omnibar />
    </div>
  )
}

