import { cn } from "@/lib/utils"
import { Icons } from "@/components/icons"

interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: "sm" | "md" | "lg"
}

const sizeClasses = {
  sm: "h-4 w-4",
  md: "h-8 w-8",
  lg: "h-12 w-12"
}

export function Spinner({ size = "md", className, ...props }: SpinnerProps) {
  return (
    <div
      role="status"
      className={cn("flex items-center justify-center", className)}
      {...props}
    >
      <Icons.spinner className={cn(
        "animate-spin text-muted-foreground",
        sizeClasses[size]
      )} />
      <span className="sr-only">Loading...</span>
    </div>
  )
} 