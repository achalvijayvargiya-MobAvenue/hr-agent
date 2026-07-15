import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useForgotPassword } from './useAuth'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const forgotPassword = useForgotPassword()

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    forgotPassword.mutate({ email })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 relative overflow-hidden font-sans">
      {/* Subtle abstract background gradient */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/20 via-zinc-950 to-zinc-950 z-0 pointer-events-none" />

      <div className="w-full max-w-md bg-zinc-900/80 backdrop-blur-md rounded-2xl border border-zinc-800 shadow-2xl p-8 relative z-10 animate-slide-up">
        <div className="mb-8 text-center animate-fade-in" style={{ animationDelay: '100ms' }}>
          <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-indigo-600">HR Platform</h1>
          <p className="mt-2 text-sm text-zinc-400">Reset your password</p>
        </div>

        {forgotPassword.isSuccess ? (
          <div className="text-center space-y-4 animate-fade-in" style={{ animationDelay: '200ms' }}>
            <div className="p-4 bg-emerald-500/10 text-emerald-400 rounded-lg border border-emerald-500/20">
              If an account exists with that email address, we have sent a password reset link to it. Please check your inbox.
            </div>
            <Link to="/login" className="block w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 hover:shadow-indigo-500/25 hover:shadow-lg transition-all duration-200">
              Return to Login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5 animate-fade-in" style={{ animationDelay: '200ms' }}>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-zinc-300 mb-1">
                Email address
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg bg-zinc-950/50 border border-zinc-700 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
                placeholder="you@example.com"
              />
            </div>

            <button
              type="submit"
              disabled={forgotPassword.isPending}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 hover:shadow-indigo-500/25 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-200"
            >
              {forgotPassword.isPending ? 'Sending...' : 'Send Reset Link'}
            </button>

            <p className="mt-6 text-center text-sm text-zinc-400 animate-fade-in" style={{ animationDelay: '300ms' }}>
              Remembered your password?{' '}
              <Link to="/login" className="font-medium text-indigo-400 hover:text-indigo-300 transition-colors">
                Log in
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
