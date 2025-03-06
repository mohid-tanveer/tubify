import { Link, useLocation } from "react-router-dom"

export function TubifyTitle() {
  const location = useLocation()
  const isHomePage = location.pathname === "/"

  return (
    <h1 className="text-white text-4xl font-bold p-10 -my-2" style={{letterSpacing: "-3px"}}>
      {isHomePage ? (
        "Tubify"
      ) : (
        <Link to="/" className="text-white text-4xl font-bold">
          Tubify
        </Link>
      )}
    </h1>
  )
} 