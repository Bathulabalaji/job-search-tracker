import { useState } from "react"

import { useSaveWeeklyTarget } from "@/api/analytics"
import type { WeeklyTarget, WeeklyTargetValues } from "@/api/types"
import { Button } from "@/components/ui/button"
import { Sheet } from "@/components/ui/sheet"
import { Stepper } from "@/components/ui/stepper"
import { Text } from "@/components/ui/text"
import { formatShortDate } from "@/lib/format"
import { toast } from "@/lib/toast-bus"

const FIELDS: readonly { name: keyof WeeklyTargetValues; label: string }[] = [
  { name: "applications", label: "Applications" },
  { name: "messages", label: "Messages" },
  { name: "referrals", label: "Referrals" },
  { name: "problems", label: "Problems solved" },
  { name: "mocks", label: "Mock interviews" },
  { name: "interviews", label: "Interviews" },
]

function valuesOf(target: WeeklyTarget | null): WeeklyTargetValues {
  return {
    applications: target?.applications ?? 0,
    messages: target?.messages ?? 0,
    referrals: target?.referrals ?? 0,
    problems: target?.problems ?? 0,
    mocks: target?.mocks ?? 0,
    interviews: target?.interviews ?? 0,
  }
}

interface Props {
  visible: boolean
  onClose: () => void
  weekStart: string
  target: WeeklyTarget | null
  carriedOver: boolean
}

export function TargetsSheet({ visible, onClose, ...rest }: Props) {
  return (
    <Sheet visible={visible} onClose={onClose} title="Weekly targets">
      {visible ? <Body onClose={onClose} {...rest} /> : null}
    </Sheet>
  )
}

function Body({ onClose, weekStart, target, carriedOver }: Omit<Props, "visible">) {
  const save = useSaveWeeklyTarget()
  const [values, setValues] = useState(() => valuesOf(target))
  // A carried-over target belongs to an earlier week: saving creates this week's own row.
  const existingId = target && !carriedOver ? target.id : null
  return (
    <>
      <Text variant="small" tone="muted">
        Week of {formatShortDate(weekStart)}
        {carriedOver ? " · starting from last week's targets" : ""}
      </Text>
      {FIELDS.map(({ name, label }) => (
        <Stepper
          key={name}
          label={label}
          value={values[name]}
          max={10_000}
          onChange={(v) => setValues((c) => ({ ...c, [name]: v }))}
        />
      ))}
      <Button
        label="Save targets"
        loading={save.isPending}
        onPress={() =>
          save.mutate(
            { existingId, weekStart, values },
            {
              onSuccess: () => {
                toast.success("Targets saved")
                onClose()
              },
              onError: (e) => toast.error("Could not save targets", e.message),
            },
          )
        }
      />
    </>
  )
}
