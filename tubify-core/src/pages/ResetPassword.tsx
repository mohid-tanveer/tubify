import { useState } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import api from "@/lib/axios"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Icons } from "@/components/icons"
import { z } from "zod"

const passwordSchema = z
  .object({
    password: z
      .string()
      .min(8, "password must be at least 8 characters")
      .regex(
        /^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&+])[A-Za-z\d@$!%*#?&+]{8,}$/,
        "password must contain at least one letter, one number, and one special character",
      ),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  })

export default function ResetPassword() {
  const [formData, setFormData] = useState({
    password: "",
    confirmPassword: "",
  })
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const { token } = useParams()
  const navigate = useNavigate()

  const validateForm = () => {
    try {
      passwordSchema.parse(formData)
      setErrors({})
      return true
    } catch (error) {
      if (error instanceof z.ZodError) {
        const newErrors: Record<string, string> = {}
        error.errors.forEach((err) => {
          if (err.path) {
            newErrors[err.path[0]] = err.message
          }
        })
        setErrors(newErrors)
      }
      return false
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validateForm()) return

    setIsLoading(true)

    try {
      await api.post(
        `/api/auth/reset-password/${token}?password=${encodeURIComponent(formData.password)}`,
      )
      setStatus("success")
    } catch (error) {
      if (process.env.NODE_ENV === "development") {
        console.error("Password reset failed:", error)
      }
      setStatus("error")
    } finally {
      setIsLoading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    const newFormData = { ...formData, [name]: value }
    setFormData(newFormData)

    // validate password in real-time
    if (name === "password") {
      try {
        z.string()
          .min(8, "password must be at least 8 characters")
          .regex(
            /^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&+])[A-Za-z\d@$!%*#?&+]{8,}$/,
            "password must contain at least one letter, one number, and one special character",
          )
          .parse(value)
        // clear password error if validation passes
        setErrors((prev) => {
          const newErrors = { ...prev }
          delete newErrors.password
          return newErrors
        })
      } catch (error) {
        if (error instanceof z.ZodError) {
          setErrors((prev) => ({
            ...prev,
            password: error.errors[0].message,
          }))
        }
      }
    }

    if (name === "confirmPassword" && value !== formData.password) {
      setErrors((prev) => ({
        ...prev,
        confirmPassword: "passwords don't match",
      }))
    } else if (
      name === "password" &&
      formData.confirmPassword &&
      value !== formData.confirmPassword
    ) {
      setErrors((prev) => ({
        ...prev,
        confirmPassword: "passwords don't match",
      }))
    } else {
      setErrors((prev) => {
        const newErrors = { ...prev }
        delete newErrors.confirmPassword
        return newErrors
      })
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
            <p className="text-sm text-white">Enter your new password below.</p>
          </div>

          <div className="mt-8">
            {status === "idle" && (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="password" className="text-white">
                    New Password
                  </Label>
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    autoCapitalize="none"
                    autoComplete="new-password"
                    disabled={isLoading}
                    value={formData.password}
                    onChange={handleInputChange}
                    className={`text-white ${errors.password ? "border-red-500 hover:border-red-600 focus:border-red-600" : ""}`}
                  />
                  {errors.password && (
                    <p className="text-sm text-red-500">{errors.password}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirmPassword" className="text-white">
                    Confirm Password
                  </Label>
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    type="password"
                    autoCapitalize="none"
                    autoComplete="new-password"
                    disabled={isLoading}
                    value={formData.confirmPassword}
                    onChange={handleInputChange}
                    className={`text-white ${errors.confirmPassword ? "border-red-500 hover:border-red-600 focus:border-red-600" : ""}`}
                  />
                  {errors.confirmPassword && (
                    <p className="text-sm text-red-500">
                      {errors.confirmPassword}
                    </p>
                  )}
                </div>
                <Button
                  variant="outline"
                  disabled={isLoading}
                  className="w-full hover:border-slate-800"
                >
                  {isLoading && (
                    <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Reset Password
                </Button>
              </form>
            )}

            {status === "success" && (
              <div className="flex flex-col space-y-2 text-center">
                <h2 className="text-xl font-semibold tracking-tight text-green-400">
                  Password Reset Successful
                </h2>
                <p className="text-sm text-white">
                  Your password has been reset. You can now sign in with your
                  new password.
                </p>
                <Button
                  className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
                  onClick={() => navigate("/auth")}
                  variant="outline"
                >
                  Sign In
                </Button>
              </div>
            )}

            {status === "error" && (
              <div className="flex flex-col space-y-2 text-center">
                <h2 className="text-xl font-semibold tracking-tight text-red-500">
                  Something went wrong
                </h2>
                <p className="text-sm text-white">
                  We couldn't reset your password. The link may have expired.
                </p>
                <Button
                  className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
                  onClick={() => navigate("/reset-password")}
                  variant="outline"
                >
                  Request New Reset Link
                </Button>
              </div>
            )}
          </div>

          <div className="mt-6 text-center">
            <Button
              variant="ghost"
              className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
              onClick={() => navigate("/auth")}
            >
              Back to Sign In
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
