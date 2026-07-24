import { useState, useEffect, useRef, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useRegister, useSendVerificationCode } from './useAuth'
import { Eye, EyeOff } from 'lucide-react'
import { Modal } from '../../components/ui/Modal'
import { FormError } from '../../components/ui/FormError'
import { getErrorMessage } from '../../lib/utils/error'

export default function RegisterPage() {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [modalError, setModalError] = useState<string | null>(null)
  const [showVerificationDialog, setShowVerificationDialog] = useState(false)
  const [verificationCode, setVerificationCode] = useState('')
  const [codeDigits, setCodeDigits] = useState<string[]>(Array(6).fill(''))
  const [timeLeft, setTimeLeft] = useState(180)
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])
  
  const register = useRegister()
  const sendVerificationCode = useSendVerificationCode()
  
  const formBackendError = getErrorMessage(sendVerificationCode.error)
  const modalBackendError = getErrorMessage(register.error)

  const handleCodeChange = (index: number, value: string) => {
    if (!/^[0-9]*$/.test(value)) return
    
    const newDigits = [...codeDigits]
    newDigits[index] = value.slice(-1)
    setCodeDigits(newDigits)
    setVerificationCode(newDigits.join(''))

    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus()
    }
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !codeDigits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const pastedData = e.clipboardData.getData('text').replace(/[^0-9]/g, '').slice(0, 6)
    if (pastedData) {
      const newDigits = [...codeDigits]
      for (let i = 0; i < 6; i++) {
        newDigits[i] = pastedData[i] || ''
      }
      setCodeDigits(newDigits)
      setVerificationCode(newDigits.join(''))
      
      const focusIndex = Math.min(pastedData.length, 5)
      inputRefs.current[focusIndex]?.focus()
    }
  }

  useEffect(() => {
    if (!showVerificationDialog) return
    if (timeLeft <= 0) return

    const timer = setInterval(() => {
      setTimeLeft(prev => prev - 1)
    }, 1000)

    return () => clearInterval(timer)
  }, [showVerificationDialog, timeLeft])

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60)
    const seconds = time % 60
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setFormError(null)

    if (!email.endsWith('@mobavenue.com')) {
      setFormError('Only @mobavenue.com email addresses are allowed.')
      return
    }

    sendVerificationCode.mutate({ email }, {
      onSuccess: () => {
        setTimeLeft(180)
        setModalError(null)
        setVerificationCode('')
        setCodeDigits(Array(6).fill(''))
        setShowVerificationDialog(true)
      },
      onError: (error: any) => {
        setFormError(getErrorMessage(error))
      }
    })
  }

  function handleVerifyAndRegister(e: FormEvent) {
    e.preventDefault()
    setModalError(null)

    register.mutate({ email, password, full_name: fullName, verification_code: verificationCode })
  }

  function handleResendCode() {
    setModalError(null)
    sendVerificationCode.mutate({ email }, {
      onSuccess: () => {
        setTimeLeft(180)
        setVerificationCode('')
        setCodeDigits(Array(6).fill(''))
      },
      onError: (error: any) => {
        setModalError(getErrorMessage(error))
      }
    })
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
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                autoComplete="new-password"
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
          </div>

          <FormError message={formError || formBackendError} />

          <button
            type="submit"
            disabled={sendVerificationCode.isPending}
            className="w-full rounded-lg bg-orange-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-orange-500 hover:shadow-orange-500/25 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-200"
          >
            {sendVerificationCode.isPending ? 'Sending code…' : 'Sign Up'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-zinc-400 animate-fade-in" style={{ animationDelay: '300ms' }}>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-orange-400 hover:text-orange-300 transition-colors">
            Sign in
          </Link>
        </p>
      </div>

      <Modal
        isOpen={showVerificationDialog}
        onClose={() => setShowVerificationDialog(false)}
        title="Verify Email"
      >
        <form onSubmit={handleVerifyAndRegister} className="space-y-6">
          <div className="space-y-6">
            <div className="text-center">
              <p className="text-sm text-zinc-300">
                We have sent a 6-digit verification code to<br />
                <strong className="text-white font-medium mt-1 inline-block">{email}</strong>
              </p>
              <p className="text-sm text-zinc-400 mt-2">
                Please enter the code below to complete your registration.
              </p>
            </div>
            
            <FormError message={modalError || modalBackendError} />

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2 text-center">
                Verification Code
              </label>
              <div className="flex justify-center gap-2 sm:gap-3" onPaste={handlePaste}>
                {codeDigits.map((digit, index) => (
                  <input
                    key={index}
                    ref={(el) => { inputRefs.current[index] = el }}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleCodeChange(index, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(index, e)}
                    className="w-12 h-14 rounded-lg bg-zinc-950/50 border border-zinc-700 text-center text-2xl font-mono text-zinc-100 placeholder-zinc-500 shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition-colors"
                  />
                ))}
              </div>
            </div>

            <div className="flex items-center justify-center pt-2">
              <span className="text-sm text-zinc-400">
                Didn't receive the code?{' '}
                {timeLeft > 0 ? (
                  <span className="text-zinc-500">Resend in {formatTime(timeLeft)}</span>
                ) : (
                  <button
                    type="button"
                    disabled={sendVerificationCode.isPending}
                    onClick={handleResendCode}
                    className="text-orange-400 font-medium hover:text-orange-300 disabled:opacity-50 transition-colors"
                  >
                    {sendVerificationCode.isPending ? 'Sending...' : 'Click to resend'}
                  </button>
                )}
              </span>
            </div>
          </div>

          <div className="flex justify-center gap-4 pt-2 mt-2 border-t border-zinc-800/50 pt-5">
            <button
              type="button"
              onClick={() => setShowVerificationDialog(false)}
              className="px-6 py-2.5 text-sm font-medium text-zinc-300 bg-zinc-800/50 hover:bg-zinc-700/50 rounded-lg transition-colors w-1/2"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={register.isPending || verificationCode.length < 6}
              className="px-6 py-2.5 text-sm font-medium text-white bg-orange-600 hover:bg-orange-500 rounded-lg shadow-sm disabled:opacity-60 disabled:cursor-not-allowed transition-colors w-1/2"
            >
              {register.isPending ? 'Verifying...' : 'Verify'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
