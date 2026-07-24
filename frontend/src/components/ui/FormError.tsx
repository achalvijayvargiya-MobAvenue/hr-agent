import { AlertCircle } from 'lucide-react'

export function FormError({ message }: { message?: string | null }) {
  if (!message) return null

  return (
    <div className="flex items-start gap-3 text-sm text-orange-400 bg-zinc-950/50 border border-orange-500/20 rounded-lg p-3 animate-fade-in shadow-sm">
      <AlertCircle className="w-5 h-5 shrink-0" />
      <p className="pt-0.5">{message}</p>
    </div>
  )
}
