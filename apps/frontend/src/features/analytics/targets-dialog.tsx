import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { useSaveWeeklyTarget } from "@/api/analytics"
import type { WeeklyTarget, WeeklyTargetValues } from "@/api/types"
import { Field } from "@/components/form/field"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { formatShortDate } from "@/lib/format"

const count = z
  .number({ error: "Enter a number" })
  .int("Whole numbers only")
  .min(0, "Cannot be negative")
  .max(10_000, "Too large")

const schema = z.object({
  applications: count,
  messages: count,
  referrals: count,
  problems: count,
  mocks: count,
  interviews: count,
})

const FIELDS: readonly { name: keyof WeeklyTargetValues; label: string }[] = [
  { name: "applications", label: "Applications" },
  { name: "messages", label: "Messages" },
  { name: "referrals", label: "Referrals" },
  { name: "problems", label: "Problems solved" },
  { name: "mocks", label: "Mock interviews" },
  { name: "interviews", label: "Interviews" },
]

const EMPTY: WeeklyTargetValues = {
  applications: 0,
  messages: 0,
  referrals: 0,
  problems: 0,
  mocks: 0,
  interviews: 0,
}

function valuesOf(target: WeeklyTarget | null): WeeklyTargetValues {
  if (!target) return EMPTY
  const { applications, messages, referrals, problems, mocks, interviews } = target
  return { applications, messages, referrals, problems, mocks, interviews }
}

interface TargetsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  weekStart: string
  /** The target in effect for this week (may be carried over from an earlier week). */
  target: WeeklyTarget | null
  carriedOver: boolean
}

export function TargetsDialog({
  open,
  onOpenChange,
  weekStart,
  target,
  carriedOver,
}: TargetsDialogProps) {
  const save = useSaveWeeklyTarget()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<WeeklyTargetValues>({
    resolver: zodResolver(schema),
    defaultValues: valuesOf(target),
  })

  useEffect(() => {
    if (open) reset(valuesOf(target))
  }, [open, target, reset])

  // A carried-over target belongs to another week: saving creates this week's own row.
  const existingId = target && !carriedOver ? target.id : null

  const onSubmit = handleSubmit((values) => {
    save.mutate(
      { existingId, weekStart, values },
      {
        onSuccess: () => {
          onOpenChange(false)
          toast.success(`Targets saved for the week of ${formatShortDate(weekStart)}`)
        },
        onError: (error) => toast.error("Could not save targets", { description: error.message }),
      },
    )
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={(event) => void onSubmit(event)} className="space-y-5" noValidate>
          <DialogHeader>
            <DialogTitle>Weekly targets</DialogTitle>
            <DialogDescription>
              Week of {formatShortDate(weekStart)}. Later weeks reuse these until you set new ones.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            {FIELDS.map(({ name, label }, index) => (
              <Field key={name} label={label} error={errors[name]?.message}>
                {(a11y) => (
                  <Input
                    {...a11y}
                    {...register(name, { valueAsNumber: true })}
                    type="number"
                    inputMode="numeric"
                    min={0}
                    className="font-mono"
                    autoFocus={index === 0}
                  />
                )}
              </Field>
            ))}
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save targets"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
