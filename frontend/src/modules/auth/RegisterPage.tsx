import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useRegister } from './useAuth'

export default function RegisterPage() {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const register = useRegister()
  
  const responseData = (register.error as any)?.response?.data
  const backendErrorDetail = responseData?.detail
  const backendErrorMessage = responseData?.message 
    || (Array.isArray(backendErrorDetail) ? backendErrorDetail[0]?.msg : backendErrorDetail)
    || (register.error as Error)?.message
    || String(register.error)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLocalError(null)

    if (!email.endsWith('@mobavenue.com')) {
      setLocalError('Only @mobavenue.com email addresses are allowed.')
      return
    }

    register.mutate({ email, password, full_name: fullName })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 relative overflow-hidden font-sans">
      {/* Subtle abstract background gradient */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-orange-900/20 via-zinc-950 to-zinc-950 z-0 pointer-events-none" />

      <div className="w-full max-w-md bg-zinc-900/80 backdrop-blur-md rounded-2xl border border-zinc-800 shadow-2xl p-8 relative z-10 animate-slide-up">
        <div className="mb-8 text-center animate-fade-in" style={{ animationDelay: '100ms' }}>
          <img src="/logo.png" alt="Logo" className="h-16 w-auto mx-auto" />
          <p className="mt-2 text-sm text-zinc-400">Create a new account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5 animate-fade-in" style={{ animationDelay: '200ms' }}>
          <div>
            <label htmlFor="fullName" className="block text-sm font-medium text-zinc-300 mb-1">
              Full Name (Optional)
            </label>
            <input
              id="fullName"
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-lg bg-zinc-950/50 border border-zinc-700 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition-colors"
              placeholder="John Doe"
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-zinc-300 mb-1">
              Email address
            </label>
            <input
              id="email"
              type="email"
              required
              pattern=".*@mobavenue\.com$"
              title="Must be a @mobavenue.com email address"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg bg-zinc-950/50 border border-zinc-700 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition-colors"
              placeholder="you@mobavenue.com"
            />
            <p className="mt-1 text-xs text-zinc-500">
              Please use your @mobavenue.com organization email
            </p>
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-zinc-300 mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg bg-zinc-950/50 border border-zinc-700 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition-colors"
              placeholder="••••••••"
            />
          </div>

          {(localError || register.isError) && (
            <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 animate-fade-in">
              {localError || backendErrorMessage || 'An error occurred during registration.'}
            </p>
          )}

          <button
            type="submit"
            disabled={register.isPending}
            className="w-full rounded-lg bg-orange-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-orange-500 hover:shadow-orange-500/25 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-200"
          >
            {register.isPending ? 'Signing up…' : 'Sign Up'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-zinc-400 animate-fade-in" style={{ animationDelay: '300ms' }}>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-orange-400 hover:text-orange-300 transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
