import * as React from "react"

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "outline" | "secondary" | "destructive"
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const baseClasses = "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2"
  
  const variantClasses = {
    default: "bg-slate-900 text-white hover:bg-slate-800",
    secondary: "bg-slate-100 text-slate-900 hover:bg-slate-200",
    destructive: "bg-red-600 text-white hover:bg-red-700",
    outline: "border border-slate-200 text-slate-700 hover:bg-slate-100",
  }
  
  const combinedClasses = `${baseClasses} ${variantClasses[variant]} ${className || ""}`
  
  return <div className={combinedClasses} {...props} />
}

export { Badge } 