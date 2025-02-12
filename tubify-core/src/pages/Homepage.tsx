import { Button } from "@/components/ui/button"
import { Link } from "react-router-dom"
import { useContext } from "react"
import { AuthContext } from "@/contexts/auth"
import { TubifyTitle } from "@/components/ui/tubify-title"

export default function Homepage() {
  const { isAuthenticated, logout } = useContext(AuthContext)

  if (isAuthenticated) {
    return (
      <div className="overflow-hidden flex flex-col min-h-screen">
        <div className="absolute top-0 left-0">
          <TubifyTitle />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <p className="text-white">Welcome to Tubify! More features coming soon...</p>
            <Button 
              onClick={logout}
              className="text-white hover:text-red-500 transition-colors"
            >
              Sign out
            </Button>
          </div>
        </div>
      </div>  
    )
  }

  return (
    <div className="overflow-hidden flex flex-col min-h-screen">
      <div className="absolute top-0 left-0">
        <TubifyTitle />
      </div>
      <div className="flex-1 flex items-center justify-center">
        <Button 
          asChild
          className="hover:text-red-500 transition-colors"
        >
          <Link to="/auth">Sign in</Link>
        </Button>
      </div>
    </div>
  )
} 