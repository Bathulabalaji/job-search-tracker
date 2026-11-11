import { AlertCircle, CheckCircle2, Info } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

interface FormAlertProps {
  tone: "error" | "success" | "info"
  children: ReactNode
  className?: string
}

const STYLES = {
  error: { box: "border-destructive/40 bg-destructive/5", icon: AlertCircle, role: "alert" },
  success: {
    box: "border-emerald-500/40 bg-emerald-500/10",
    icon: CheckCircle2,
    role: "status",
  },
  info: { box: "border-primary/30 bg-primary/5", icon: Info, role: "status" },
} as const

export function FormAlert({ tone, children, className }: FormAlertProps) {
  const { box, icon: Icon, role } = STYLES[tone]
  return (
    <div
      role={role}
      className={cn(
        "flex items-start gap-2.5 rounded-lg border px-3.5 py-3 text-sm",
        box,
        className,
      )}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}
