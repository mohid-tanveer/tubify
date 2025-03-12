import { useEffect, useState, useRef, useContext } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '@/lib/axios'
import { Button } from "@/components/ui/button"
import { AuthContext } from "@/contexts/auth"
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
    <div className="min-h-screen w-full flex items-center justify-center">
      <div className="w-full max-w-md mx-auto px-4">
        {status === 'loading' && (
          <div className="flex flex-col space-y-2 text-center">
            <h1 className="text-2xl font-semibold tracking-tight text-white">
              Verifying your email...
            </h1>
            <p className="text-sm text-white">
              Please wait while we verify your email address.
            </p>
          </div>
        )}

        {status === 'success' && (
          <div className="flex flex-col space-y-2 text-center">
            <h1 className="text-2xl font-semibold tracking-tight text-green-400">
              Email Verified!
            </h1>
            <p className="text-sm text-white">
              Your email has been successfully verified.
            </p>
            <Button
              className="mt-4 mx-auto"
              onClick={() => navigate('/')}
            >
              Back to homepage
            </Button>
          </div>
        )}

        {status === 'error' && (
          <div className="flex flex-col space-y-2 text-center">
            <h1 className="text-2xl font-semibold tracking-tight text-red-600">
              Verification Failed
            </h1>
            <p className="text-sm text-white">
              The verification link is invalid or has expired. Please request a new verification email.
            </p>
            <Button
              className="mt-4 mx-auto"
              onClick={() => navigate('/auth')}
              variant="outline"
            >
              Back to Sign In
            </Button>
          </div>
        )}
      </div>
    </div>
  )
} 