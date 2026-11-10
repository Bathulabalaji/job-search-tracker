import { zodResolver } from "@hookform/resolvers/zod"
import { NotebookPen } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { useCreateDailyLog, useUpdateDailyLog } from "@/api/daily-logs"
import type { DailyLog } from "@/api/types"
import { Field } from "@/components/form/field"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { formatDate } from "@/lib/format"

const count = z
  .number({ error: "Enter a number" })
  .int("Whole numbers only")
  .min(0, "Cannot be negative")
  .max(10_000, "Too large")

const schema = z.object({
  applications_sent: count,
  messages_sent: count,
  referrals_requested: count,
  problems_solved: count,
  mocks_done: count,
  hours_prep: z
    .number({ error: "Enter a number" })
    .min(0, "Cannot be negative")
    .max(24, "At most 24 hours"),
  notes: z.string().max(4000),
})
type Values = z.infer<typeof schema>

const COUNT_FIELDS = [
  { name: "applications_sent", label: "Applications sent" },
  { name: "messages_sent", label: "Messages sent" },
  { name: "referrals_requested", label: "Referrals requested" },
  { name: "problems_solved", label: "Problems solved" },
  { name: "mocks_done", label: "Mocks done" },
] as const

function defaults(log: DailyLog | undefined): Values {
  return {
    applications_sent: log?.applications_sent ?? 0,
    messages_sent: log?.messages_sent ?? 0,
    referrals_requested: log?.referrals_requested ?? 0,
    problems_solved: log?.problems_solved ?? 0,
    mocks_done: log?.mocks_done ?? 0,
    hours_prep: log?.hours_prep ?? 0,
    notes: log?.notes ?? "",
  }
}

interface LogFormProps {
  date: string
  existing: DailyLog | undefined
}

/** Mount with a `key` that changes with the date/log so fields reset cleanly. */
export function LogForm({ date, existing }: LogFormProps) {
  const create = useCreateDailyLog()
  const update = useUpdateDailyLog()
  const [showNotes, setShowNotes] = useState(Boolean(existing?.notes))
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults(existing) })

  const saving = create.isPending || update.isPending
  const done = () => toast.success(`${existing ? "Updated" : "Logged"} ${formatDate(date)}`)
  const failed = (error: Error) => toast.error("Could not save log", { description: error.message })

  const onSubmit = handleSubmit((values) => {
    const notes = values.notes.trim() === "" ? null : values.notes.trim()
    const { notes: _ignored, ...counts } = values
    if (existing) {
      update.mutate(
        { id: existing.id, patch: { ...counts, notes } },
        { onSuccess: done, onError: failed },
      )
    } else {
      create.mutate({ log_date: date, ...counts, notes }, { onSuccess: done, onError: failed })
    }
  })

  return (
    <form onSubmit={(event) => void onSubmit(event)} noValidate className="space-y-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        {COUNT_FIELDS.map(({ name, label }, index) => (
          <Field key={name} label={label} error={errors[name]?.message}>
            {(a11y) => (
              <Input
                {...a11y}
                {...register(name, { valueAsNumber: true })}
                type="number"
                inputMode="numeric"
                min={0}
                className="h-11 font-mono text-lg"
                autoFocus={index === 0}
              />
            )}
          </Field>
        ))}
        <Field label="Hours of prep" error={errors.hours_prep?.message}>
          {(a11y) => (
            <Input
              {...a11y}
              {...register("hours_prep", { valueAsNumber: true })}
              type="number"
              inputMode="decimal"
              min={0}
              max={24}
              step={0.5}
              className="h-11 font-mono text-lg"
            />
          )}
        </Field>
      </div>

      {showNotes ? (
        <Field label="Note (optional)" error={errors.notes?.message}>
          {(a11y) => <Textarea {...a11y} {...register("notes")} rows={3} />}
        </Field>
      ) : (
        <Button type="button" variant="ghost" size="sm" onClick={() => setShowNotes(true)}>
          <NotebookPen />
          Add a note
        </Button>
      )}

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : existing ? "Update log" : "Save log"}
        </Button>
        <p className="text-sm text-muted-foreground">
          {existing ? "Editing the saved log for this day." : "Zeros are fine on a rest day."}
        </p>
      </div>
    </form>
  )
}
