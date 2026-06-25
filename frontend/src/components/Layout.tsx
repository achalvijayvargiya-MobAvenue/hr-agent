import Sidebar from './Sidebar'

interface Props {
  children: React.ReactNode
}

export default function Layout({ children }: Props) {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden p-8">{children}</main>
    </div>
  )
}
