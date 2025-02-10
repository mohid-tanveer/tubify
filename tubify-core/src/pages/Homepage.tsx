import { Button } from "@/components/ui/button"
import { Link } from "react-router-dom"

export default function Homepage() {
  return (
    <div className="overflow-hidden flex flex-col">
      <h1 className="text-white text-4xl font-bold p-3 -my-2">Tubify</h1>
      <div className="absolute inset-0 flex items-center justify-center">
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