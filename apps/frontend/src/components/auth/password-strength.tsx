import { Check, Circle } from "lucide-react"

import { passwordChecks } from "@/features/auth/password-policy"
import { cn } from "@/lib/utils"

/** Live checklist under a password field. Meaning is carried by the icon and text, not colour. */
export function PasswordStrength({ password }: { password: string }) {
  if (!password) return null
  const checks = passwordChecks(password)
  return (
    <ul className="space-y-1 text-xs" aria-label="Password requirements">
      {checks.map((check) => (
        <li
          key={check.label}
          className={cn(
            "flex items-center gap-1.5",
            check.met ? "text-emerald-700 dark:text-emerald-300" : "text-muted-foreground",
          )}
        >
          {check.met ? (
            <Check className="size-3.5" aria-hidden />
          ) : (
            <Circle className="size-3.5" aria-hidden />
          )}
          <span>{check.label}</span>
          <span className="sr-only">{check.met ? "(met)" : "(not met yet)"}</span>
        </li>
      ))}
    </ul>
  )
}
