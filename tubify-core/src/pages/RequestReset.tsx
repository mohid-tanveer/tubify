import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '@/lib/axios'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Icons } from "@/components/icons"

export default function RequestReset() {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await api.post(`/api/auth/reset-password/request?email=${encodeURIComponent(email)}`)
      setStatus('success')
    } catch (error) {
      console.error('Password reset request failed:', error)
      setStatus('error')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden lg:block bg-zinc-900">
        <div className="flex h-full flex-col">
          <div className="flex items-center text-lg p-10 font-medium text-white">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="mr-2 h-6 w-6"
            >
              <path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3" />
            </svg>
            <Link to="/" className="text-white hover:text-slate-300">
              Tubify
            </Link>
          </div>
          <div className="mt-auto p-10">
            <blockquote className="space-y-2">
              <p className="text-lg text-white">
                &ldquo;Transform your Spotify experience with Tubify.&rdquo;
              </p>
            </blockquote>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-center bg-black">
        <div className="mx-auto w-full max-w-sm px-8">
          <div className="flex flex-col space-y-2 text-center">
            <h1 className="text-2xl font-semibold tracking-tight text-white">
              Reset your password
            </h1>
            <p className="text-sm text-white">
              Enter your email address and we'll send you a link to reset your password.
            </p>
          </div>

          <div className="mt-8">
            {status === 'idle' && (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-white">Email</Label>
                  <Input
                    id="email"
                    placeholder="name@example.com"
                    type="email"
                    autoCapitalize="none"
                    autoComplete="email"
                    autoCorrect="off"
                    disabled={isLoading}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="text-white"
                  />
                </div>
                <Button 
                  variant="outline" 
                  disabled={isLoading}
                  className="w-full hover:border-slate-800"
                >
                  {isLoading && (
                    <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Send Reset Link
                </Button>
              </form>
            )}

            {status === 'success' && (
              <div className="flex flex-col space-y-2 text-center">
                <h2 className="text-xl font-semibold tracking-tight text-green-400">
                  Check your email
                </h2>
                <p className="text-sm text-white">
                  We've sent you a password reset link. Please check your email.
                </p>
                <Button
                  className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
                  onClick={() => navigate('/auth')}
                  variant="outline"
                >
                  Back to Sign In
                </Button>
              </div>
            )}

            {status === 'error' && (
              <div className="flex flex-col space-y-2 text-center">
                <h2 className="text-xl font-semibold tracking-tight text-red-500">
                  Something went wrong
                </h2>
                <p className="text-sm text-white">
                  We couldn't send the reset link. Please try again.
                </p>
                <Button
                  className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
                  onClick={() => setStatus('idle')}
                  variant="outline"
                >
                  Try Again
                </Button>
              </div>
            )}
          </div>

          <div className="mt-6 text-center">
            <Button
              variant="ghost"
              className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
              onClick={() => navigate('/auth')}
            >
              Back to Sign In
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
} 