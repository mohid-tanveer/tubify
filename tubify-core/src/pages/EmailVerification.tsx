import { useEffect, useState, useRef, useContext } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '@/lib/axios'
import { Button } from "@/components/ui/button"
import { AuthContext } from "@/contexts/auth"
import { TubifyTitle } from "@/components/ui/tubify-title"
import { Icons } from "@/components/icons"
import { CheckCircle, XCircle } from "lucide-react"
import { toast } from 'sonner'

export default function EmailVerification() {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const { token } = useParams()
  const navigate = useNavigate()
  const verificationAttempted = useRef(false)
  const { login } = useContext(AuthContext)

  useEffect(() => {
    const verifyEmail = async () => {
      if (verificationAttempted.current) return
      verificationAttempted.current = true
      
      try {
        // add a small delay to ensure the backend has time to process
        await new Promise(resolve => setTimeout(resolve, 500))
        
        const response = await api.get(`/api/auth/verify-email/${token}`)
        
        // check for success message from backend
        if (response.data && (
            response.data.message === "Email already verified" || 
            response.data.message === "Email verified successfully")) {
          setStatus('success')
          // refresh auth state
          await login()
          toast.success(response.data.message)
        } else {
          if (process.env.NODE_ENV === "development") {
            console.error('Unexpected response:', response.data)
          }
          setStatus('error')
          toast.error('Verification failed with unexpected response')
        }
      } catch (error) {
        if (process.env.NODE_ENV === "development") {
          console.error('Email verification failed:', error)
        }
        setStatus('error')
        toast.error('Verification failed. The link may be invalid or expired.')
      }
    }

    verifyEmail()
  }, [token, login])

  return (
    <div className="scrollable-page bg-linear-to-b from-slate-900 to-black min-h-screen">
      <div className="relative sm:absolute top-0 left-0">
        <TubifyTitle />
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-34 sm:pt-60">
        <div className="flex flex-col items-center justify-center">
          {status === 'loading' && (
            <div className="w-full max-w-md p-6 rounded-lg border border-slate-700 bg-slate-900/50 shadow-lg text-center">
              <div className="flex flex-col items-center space-y-6">
                <Icons.spinner className="h-12 w-12 animate-spin text-slate-400" />
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight text-white">
                    Verifying your email...
                  </h1>
                  <p className="mt-2 text-sm text-slate-400">
                    Please wait while we verify your email address.
                  </p>
                </div>
              </div>
            </div>
          )}

          {status === 'success' && (
            <div className="w-full max-w-md p-6 rounded-lg border border-slate-700 bg-slate-900/50 shadow-lg text-center">
              <div className="flex flex-col items-center space-y-4">
                <div className="h-16 w-16 rounded-full bg-green-500/20 flex items-center justify-center">
                  <CheckCircle className="h-8 w-8 text-green-500" />
                </div>
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight text-white">
                    Email Verified!
                  </h1>
                  <p className="mt-2 text-sm text-slate-400">
                    Your email has been successfully verified.
                  </p>
                </div>
                <Button
                  className="mt-4 w-full"
                  onClick={() => navigate('/')}
                >
                  Back to homepage
                </Button>
              </div>
            </div>
          )}

          {status === 'error' && (
            <div className="w-full max-w-md p-6 rounded-lg border border-slate-700 bg-slate-900/50 shadow-lg text-center">
              <div className="flex flex-col items-center space-y-4">
                <div className="h-16 w-16 rounded-full bg-red-500/20 flex items-center justify-center">
                  <XCircle className="h-8 w-8 text-red-500" />
                </div>
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight text-white">
                    Verification Failed
                  </h1>
                  <p className="mt-2 text-sm text-slate-400">
                    The verification link is invalid or has expired.
                  </p>
                </div>
                <div className="flex flex-col sm:flex-row gap-3 w-full">
                  <Button
                    variant="outline"
                    className="w-full border-slate-700 text-slate-300 hover:text-white hover:bg-slate-800"
                    onClick={() => navigate('/auth')}
                  >
                    Back to Sign In
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
} 