import { Command } from "lucide-react"
import { Link } from "react-router-dom"

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 rounded-md font-semibold tracking-tight">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-lg shadow-primary/30">
        <Command className="size-4" aria-hidden />
      </span>
      Career Command Center
    </Link>
  )
}
