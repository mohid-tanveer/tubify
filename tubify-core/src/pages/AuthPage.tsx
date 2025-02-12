import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Icons } from "@/components/icons"
import { useState, useContext, useEffect, useRef } from "react"
import { useNavigate, useLocation, Link } from "react-router-dom"
import api from "@/lib/axios"
import { z } from "zod"
import { AxiosError } from "axios"
import { AuthContext } from "@/contexts/auth"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Eye, EyeOff } from "lucide-react"

const loginSchema = z.object({
  email: z.string().min(1, "email or username is required"),
  password: z.string().min(1, "password is required"),
})

const registerSchema = z.object({
  email: z.string().email("please enter a valid email address"),
  username: z.string()
    .min(3, "username must be at least 3 characters")
    .max(50, "username must be less than 50 characters"),
  password: z.string()
    .min(8, "password must be at least 8 characters")
    .regex(
      /^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&+])[A-Za-z\d@$!%*#?&+]{8,}$/,
      "password must contain at least one letter, one number, and one special character"
    ),
})

type RegisterFormValues = z.infer<typeof registerSchema>

interface UserAuthFormProps extends React.HTMLAttributes<HTMLDivElement> {
  type: "login" | "register"
}

export default function AuthPage() {
  const [authType, setAuthType] = useState<"login" | "register">("login")
  const { login } = useContext(AuthContext)
  const location = useLocation()
  const navigate = useNavigate()
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isProcessingOAuth, setIsProcessingOAuth] = useState(false)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const processingRef = useRef(false)

  useEffect(() => {
    // handle OAuth callback
    const params = new URLSearchParams(location.search)
    const code = params.get("code")
    const error = params.get("error")

    if (error) {
      console.error("OAuth error:", error)
      setErrors(prev => ({
        ...prev,
        oauth: `Authentication failed: ${error}`
      }))
      navigate("/auth")
      return
    }

    if (code && !processingRef.current) {
      const handleOAuthCallback = async () => {
        if (processingRef.current) return
        processingRef.current = true
        setIsProcessingOAuth(true)

        try {
          // Clear the URL to prevent reuse of the code
          window.history.replaceState({}, document.title, "/auth")
          
          const provider = location.pathname.includes("google")
            ? "google"
            : "github"
            
          console.log(`Attempting ${provider} OAuth callback with code:`, code)
          const response = await api.get(`/api/auth/${provider}/callback`, {
            params: { code }
          })
          
          console.log("OAuth callback response:", response.data)
          if (response.data?.message === "Authentication successful") {
            setIsAuthenticated(true)
            login()
            navigate("/")
          } else {
            throw new Error("Authentication response was not successful")
          }
        } catch (error) {
          console.error("OAuth callback failed:", error)
          const axiosError = error as AxiosError<{ detail: string }>
          const errorMessage = axiosError.response?.data?.detail || "Authentication failed. Please try again."
          console.error("Detailed error:", errorMessage)
          setErrors(prev => ({
            ...prev,
            oauth: errorMessage
          }))
        } finally {
          setIsProcessingOAuth(false)
          processingRef.current = false
        }
      }
      
      handleOAuthCallback()
    }
  }, [location, login, navigate])
  
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {errors?.oauth && (
        <div className="absolute top-4 right-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {errors.oauth}
        </div>
      )}
      {isProcessingOAuth && !isAuthenticated && (
        <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <div className="bg-white p-4 rounded-lg">
            <div className="flex justify-center">
              <Icons.spinner className="h-8 w-8 animate-spin text-black" />
            </div>
            <p className="mt-2 text-black">Processing authentication...</p>
          </div>
        </div>
      )}
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
              {authType === "login" ? "Welcome back" : "Create an account"}
            </h1>
            <p className="text-sm text-white">
              {authType === "login" 
                ? "Enter your credentials to sign in" 
                : "Enter your information to create an account"}
            </p>
          </div>
          <UserAuthForm type={authType} />
          <p className="px-8 text-center text-sm">
            {authType === "login" ? (
              <>
                <br /><span className="text-white">Don't have an account?&nbsp;&nbsp;</span>
                <Button 
                  variant="outline"
                  className="hover:border-slate-800"
                  onClick={() => setAuthType("register")}
                >
                  Sign up
                </Button>
              </>
            ) : (
              <>
                <br /><span className="text-white">Have an account?&nbsp;&nbsp;</span>
                <Button 
                  variant="outline"
                  className="hover:border-slate-800"
                  onClick={() => setAuthType("login")}
                >
                  Sign in
                </Button>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}

function UserAuthForm({ type, ...props }: UserAuthFormProps) {
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [showPassword, setShowPassword] = useState(false)
  const [isCheckingUsername, setIsCheckingUsername] = useState(false)
  const navigate = useNavigate()
  const { login } = useContext(AuthContext)
  const usernameCheckTimeout = useRef<NodeJS.Timeout>()

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(type === "login" ? loginSchema : registerSchema),
    defaultValues: {
      email: "",
      ...(type === "register" ? { username: "" } : {}),
      password: "",
    } as RegisterFormValues,
    mode: "onChange",
  })

  const watchedUsername = form.watch("username")

  // check username availability
  useEffect(() => {
    if (type !== "register") return

    const username = watchedUsername
    if (!username || username.length < 3) return

    // clear any existing timeout
    if (usernameCheckTimeout.current) {
      clearTimeout(usernameCheckTimeout.current)
    }

    // set a new timeout to check username
    usernameCheckTimeout.current = setTimeout(async () => {
      try {
        setIsCheckingUsername(true)
        const response = await api.get(`/api/auth/check-username/${username}`)
        if (!response.data.available) {
          form.setError("username", {
            type: "manual",
            message: "this username is already taken"
          })
        }
      } catch (error) {
        console.error("Failed to check username:", error)
      } finally {
        setIsCheckingUsername(false)
      }
    }, 500) // debounce for 500ms

    return () => {
      if (usernameCheckTimeout.current) {
        clearTimeout(usernameCheckTimeout.current)
      }
    }
  }, [watchedUsername, type, form])

  async function onSubmit(data: RegisterFormValues) {
    setIsLoading(true)

    try {
      const endpoint = type === "login" ? "/api/auth/login" : "/api/auth/register"
      
      if (type === "login") {
        // for login, use URLSearchParams format as required by OAuth2PasswordRequestForm
        const params = new URLSearchParams()
        params.append("username", data.email) // email field contains either email or username
        params.append("password", data.password)
        const response = await api.post(endpoint, params, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        })
        
        if (!response.data?.access_token) {
          throw new Error("no access token received")
        }
      } else {
        // for register, use JSON format
        await api.post(endpoint, data)
      }
      
      await login()
      navigate("/")
    } catch (err) {
      console.error("login error:", err)
      if (err instanceof AxiosError && err.response?.data) {
        const errorMessage = typeof err.response.data.detail === 'string' 
          ? err.response.data.detail 
          : "authentication failed"
        form.setError("root", { message: errorMessage })
      } else {
        form.setError("root", { message: "something went wrong" })
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleOAuthLogin = async (provider: "google" | "github") => {
    try {
      const response = await api.get(`/api/auth/${provider}`)
      window.location.href = response.data.url
    } catch (err) {
      console.error(err)
      form.setError("root", { message: "failed to initialize oauth login" })
    }
  }

  return (
    <div className="grid gap-6" {...props}>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-2">
          {type === "register" && (
            <FormField
              control={form.control}
              name="username"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-white">Username</FormLabel>
                  <FormControl>
                    <div className="relative">
                      <Input
                        {...field}
                        placeholder="johndoe"
                        type="text"
                        autoCapitalize="none"
                        autoCorrect="off"
                        disabled={isLoading}
                        className={`text-white ${form.formState.errors.username ? 'border-red-500 hover:border-red-600 focus:border-red-600' : ''}`}
                      />
                      {isCheckingUsername && (
                        <Icons.spinner className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-gray-500" />
                      )}
                    </div>
                  </FormControl>
                  <FormMessage className="text-red-500" />
                </FormItem>
              )}
            />
          )}
          
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-white">
                  {type === "login" ? "Email or username" : "Email"}
                </FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    placeholder={type === "login" ? "name@example.com or username" : "name@example.com"}
                    type={type === "login" ? "text" : "email"}
                    autoCapitalize="none"
                    autoComplete={type === "login" ? "username" : "email"}
                    autoCorrect="off"
                    disabled={isLoading}
                    className={`text-white ${form.formState.errors.email ? 'border-red-500 hover:border-red-600 focus:border-red-600' : ''}`}
                  />
                </FormControl>
                <FormMessage className="text-red-500" />
              </FormItem>
            )}
          />
          
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-white">Password</FormLabel>
                <FormControl>
                  <div className="relative">
                    <Input
                      {...field}
                      placeholder="********"
                      type={showPassword ? "text" : "password"}
                      autoCapitalize="none"
                      autoComplete={type === "login" ? "current-password" : "new-password"}
                      disabled={isLoading}
                      className={`text-white pr-10 ${form.formState.errors.password ? 'border-red-500 hover:border-red-600 focus:border-red-600' : ''}`}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8 p-0 hover:bg-transparent hover:border-slate-800"
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex={-1}
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4 text-gray-500" />
                      ) : (
                        <Eye className="h-4 w-4 text-gray-500" />
                      )}
                    </Button>
                  </div>
                </FormControl>
                <FormMessage className="text-red-500" />
                {type === "login" && (
                  <Link 
                    to="/reset-password"
                    className="text-sm text-white hover:text-slate-300 block mt-2"
                  >
                    forgot password?
                  </Link>
                )}
              </FormItem>
            )}
          />
          
          {form.formState.errors.root && (
            <p className="text-sm text-red-500">{form.formState.errors.root.message}</p>
          )}
          <Button variant="outline" className="w-full hover:border-slate-800" disabled={isLoading}>
            {isLoading && (
              <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
            )}
            {type === "login" ? "Sign in" : "Sign up"}
          </Button>
        </form>
      </Form>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t border-neutral-900" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-black px-2 text-white">
            Or continue with
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Button 
          onClick={() => handleOAuthLogin("google")}
          variant='outline'
          disabled={isLoading}
          className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
        >
          {isLoading ? (
            <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Icons.google className="mr-2 h-4 w-4" />
          )}
          Google
        </Button>
        <Button 
          onClick={() => handleOAuthLogin("github")} 
          variant='outline'
          disabled={isLoading}
          className="bg-black hover:bg-neutral-900 border-slate-800 hover:border-slate-600 hover:text-slate-300 text-white"
        >
          {isLoading ? (
            <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Icons.gitHub className="mr-2 h-4 w-4" />
          )}
          GitHub
        </Button>
      </div>
    </div>
  )
}