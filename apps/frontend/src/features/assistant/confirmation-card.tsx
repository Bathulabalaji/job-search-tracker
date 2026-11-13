import { Check, ClipboardCheck, X } from "lucide-react"
import { useState } from "react"

import type { ActionField, PendingAction } from "@/api/chat"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface Props {
  action: PendingAction
  busy: boolean
  onConfirm: (edits: Record<string, unknown>) => void
  onReject: () => void
}

function initial(field: ActionField): string {
  const value = field.value
  if (value === null || value === undefined) return ""
  if (field.type === "datetime" && typeof value === "string") return value.slice(0, 16)
  return String(value)
}

/**
 * The assistant proposed a change. Nothing happens until Confirm; editable fields can be
 * adjusted first, and only changed ones are sent back.
 */
export function ConfirmationCard({ action, busy, onConfirm, onReject }: Props) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(action.fields.map((f) => [f.name, initial(f)])),
  )
  const edits = (): Record<string, unknown> => {
    const changed: Record<string, unknown> = {}
    for (const field of action.fields) {
      if (!field.editable) continue
      const now = values[field.name] ?? ""
      if (now !== initial(field)) changed[field.name] = field.type === "number" ? Number(now) : now
    }
    return changed
  }
  const set = (name: string, value: string) => setValues((v) => ({ ...v, [name]: value }))
  const inputClass = "h-8 text-sm"

  return (
    <section
      aria-label="Confirm this change"
      className="mt-2 max-w-md rounded-lg border bg-card p-3 text-sm shadow-sm"
    >
      <div className="mb-2 flex items-start gap-2">
        <ClipboardCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        <div className="min-w-0">
          <p className="font-medium">{action.title}</p>
          <p className="text-muted-foreground">{action.summary}</p>
        </div>
      </div>
      {action.warning ? (
        <p className="mb-2 rounded bg-amber-500/10 px-2 py-1 text-xs text-amber-700 dark:text-amber-300">
          {action.warning}
        </p>
      ) : null}
      <dl className="mb-3 grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5">
        {action.fields.map((field) => {
          const id = `${action.id}-${field.name}`
          const value = values[field.name] ?? ""
          return (
            <div key={field.name} className="contents">
              <dt>
                <Label htmlFor={id} className="text-xs text-muted-foreground">
                  {field.label}
                </Label>
              </dt>
              <dd className="min-w-0">
                {!field.editable ? (
                  <span>{value || "—"}</span>
                ) : field.type === "select" ? (
                  <select
                    id={id}
                    value={value}
                    disabled={busy}
                    onChange={(e) => set(field.name, e.target.value)}
                    className="h-8 w-full rounded-md border bg-background px-2 text-sm"
                  >
                    {(field.options ?? []).map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    id={id}
                    value={value}
                    disabled={busy}
                    className={inputClass}
                    type={
                      field.type === "date"
                        ? "date"
                        : field.type === "datetime"
                          ? "datetime-local"
                          : field.type === "number"
                            ? "number"
                            : "text"
                    }
                    onChange={(e) => set(field.name, e.target.value)}
                  />
                )}
              </dd>
            </div>
          )
        })}
      </dl>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={busy} onClick={() => onConfirm(edits())}>
          <Check /> Confirm
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={onReject}>
          <X /> Decline
        </Button>
      </div>
    </section>
  )
}
