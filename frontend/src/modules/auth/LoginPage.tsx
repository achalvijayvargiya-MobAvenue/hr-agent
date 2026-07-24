import { useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useLogin } from './useAuth'
import { Eye, EyeOff } from 'lucide-react'
import { FormError } from '../../components/ui/FormError'
import { FormSuccess } from '../../components/ui/FormSuccess'
import { getErrorMessage } from '../../lib/utils/error'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const login = useLogin()
  const location = useLocation()
  const successMessage = (location.state as any)?.successMessage

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    login.mutate({ email, password })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 relative overflow-hidden font-sans">
      {/* Subtle abstract background gradient */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-orange-900/20 via-zinc-950 to-zinc-950 z-0 pointer-events-none" />

      <div className="w-full max-w-md bg-zinc-900/80 backdrop-blur-md rounded-2xl border border-zinc-800 shadow-2xl p-8 relative z-10 animate-slide-up">
        <div className="mb-8 text-center animate-fade-in" style={{ animationDelay: '100ms' }}>
          <img src="/logo.png" alt="Logo" className="h-16 w-auto mx-auto" />
          <p className="mt-2 text-sm text-zinc-400">Sign in to your account</p>
        </div>

        <FormSuccess message={successMessage} />

        <form onSubmit={handleSubmit} className="space-y-5 animate-fade-in" style={{ animationDelay: '200ms' }}>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-zinc-300 mb-1">
              Email address
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg bg-zinc-950/50 border border-zinc-700 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition-colors"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-zinc-300 mb-1">
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg bg-zinc-950/50 border border-zinc-700 px-3 py-2 pr-10 text-sm text-zinc-100 placeholder-zinc-500 shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition-colors"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-zinc-400 hover:text-zinc-300 focus:outline-none"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            <div className="flex items-center justify-end mt-2">
              <div className="text-sm">
                <Link to="/forgot-password" className="font-medium text-orange-400 hover:text-orange-300 transition-colors">
                  Forgot your password?
                </Link>
              </div>
            </div>
          </div>

          <FormError message={getErrorMessage(login.error)} />

          <button
            type="submit"
            disabled={login.isPending}
            className="w-full rounded-lg bg-orange-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-orange-500 hover:shadow-orange-500/25 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-200"
          >
            {login.isPending ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-zinc-400 animate-fade-in" style={{ animationDelay: '300ms' }}>
          Don't have an account?{' '}
          <Link to="/register" className="font-medium text-orange-400 hover:text-orange-300 transition-colors">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  )
}
