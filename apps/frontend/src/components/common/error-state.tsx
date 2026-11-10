import { AlertTriangle } from "lucide-react"

import { Button } from "@/components/ui/button"

interface ErrorStateProps {
  message: string
  onRetry?: () => void
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-6 py-8 text-center"
    >
      <AlertTriangle className="size-5 text-destructive" aria-hidden />
      <p className="font-medium">Something went wrong</p>
      <p className="max-w-md text-sm text-muted-foreground">{message}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  )
}
