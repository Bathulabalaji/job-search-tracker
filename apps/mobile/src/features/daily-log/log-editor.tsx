import { useState } from "react"
import { View } from "react-native"

import { useCreateDailyLog, useUpdateDailyLog } from "@/api/daily-logs"
import type { DailyLog, DailyLogCounts } from "@/api/types"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Stepper } from "@/components/ui/stepper"
import { TextField } from "@/components/ui/text-field"
import { formatDate } from "@/lib/format"
import { toast } from "@/lib/toast-bus"

const COUNT_FIELDS = [
  { name: "applications_sent", label: "Applications sent" },
  { name: "messages_sent", label: "Messages sent" },
  { name: "referrals_requested", label: "Referrals requested" },
  { name: "problems_solved", label: "Problems solved" },
  { name: "mocks_done", label: "Mocks done" },
] as const

function initial(log: DailyLog | undefined): DailyLogCounts {
  return {
    applications_sent: log?.applications_sent ?? 0,
    messages_sent: log?.messages_sent ?? 0,
    referrals_requested: log?.referrals_requested ?? 0,
    problems_solved: log?.problems_solved ?? 0,
    mocks_done: log?.mocks_done ?? 0,
    hours_prep: log?.hours_prep ?? 0,
  }
}

/** Mount with a `key` that changes with the date, so the numbers reset cleanly. */
export function LogEditor({ date, existing }: { date: string; existing: DailyLog | undefined }) {
  const create = useCreateDailyLog()
  const update = useUpdateDailyLog()
  const [counts, setCounts] = useState<DailyLogCounts>(() => initial(existing))
  const [notes, setNotes] = useState(existing?.notes ?? "")
  const saving = create.isPending || update.isPending

  const save = () => {
    const cleanNotes = notes.trim() === "" ? null : notes.trim()
    const done = () => toast.success(`${existing ? "Updated" : "Logged"} ${formatDate(date)}`)
    const failed = (error: Error) => toast.error("Could not save log", error.message)
    if (existing) {
      update.mutate({ id: existing.id, patch: { ...counts, notes: cleanNotes } }, { onSuccess: done, onError: failed })
    } else {
      create.mutate({ log_date: date, ...counts, notes: cleanNotes }, { onSuccess: done, onError: failed })
    }
  }

  return (
    <View style={{ gap: 14 }}>
      <Card style={{ gap: 16 }}>
        {COUNT_FIELDS.map(({ name, label }) => (
          <Stepper
            key={name}
            label={label}
            value={counts[name]}
            max={10_000}
            onChange={(value) => setCounts((c) => ({ ...c, [name]: value }))}
          />
        ))}
        <Stepper
          label="Hours of prep"
          value={counts.hours_prep}
          max={24}
          step={0.5}
          decimal
          onChange={(value) => setCounts((c) => ({ ...c, hours_prep: value }))}
        />
      </Card>
      <TextField label="Notes (optional)" value={notes} onChangeText={setNotes} multiline maxLength={4000} />
      <Button label={existing ? "Update log" : "Save log"} icon="save-outline" loading={saving} onPress={save} />
    </View>
  )
}
