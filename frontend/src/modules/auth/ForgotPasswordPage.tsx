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
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-md p-8">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-indigo-600">HR Platform</h1>
          <p className="mt-1 text-sm text-gray-500">Reset your password</p>
        </div>

        {forgotPassword.isSuccess ? (
          <div className="text-center space-y-4">
            <div className="p-4 bg-green-50 text-green-700 rounded-lg border border-green-200">
              If an account exists with that email address, we have sent a password reset link to it. Please check your inbox.
            </div>
            <Link to="/login" className="block w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-indigo-700">
              Return to Login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email address
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="you@example.com"
              />
            </div>

            <button
              type="submit"
              disabled={forgotPassword.isPending}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {forgotPassword.isPending ? 'Sending...' : 'Send Reset Link'}
            </button>

            <p className="mt-6 text-center text-sm text-gray-500">
              Remembered your password?{' '}
              <Link to="/login" className="font-medium text-indigo-600 hover:text-indigo-500">
                Log in
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
