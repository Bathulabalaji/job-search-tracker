import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { useCreateInteraction } from "@/api/interactions"
import { ApiError } from "@/api/client"
import { DIRECTIONS, LOGGABLE_INTERACTION_TYPES } from "@/api/types"
import { Button } from "@/components/ui/button"
import { FormSelect, FormText } from "@/components/ui/form"
import { Sheet } from "@/components/ui/sheet"
import { titleCase } from "@/lib/format"
import { toast } from "@/lib/toast-bus"
import { useState } from "react"
import { FormAlert } from "@/components/auth/auth-shell"

const schema = z.object({
  type: z.enum(LOGGABLE_INTERACTION_TYPES),
  direction: z.enum(DIRECTIONS),
  summary: z.string().max(2000),
})
type Values = z.infer<typeof schema>

const TYPE_OPTIONS = LOGGABLE_INTERACTION_TYPES.map((value) => ({ value, label: titleCase(value) }))
const DIRECTION_OPTIONS = [
  { value: "out", label: "Outgoing (I reached out)" },
  { value: "in", label: "Incoming (they reached out)" },
] as const

export function LogInteractionSheet({
  visible,
  onClose,
  opportunityId,
}: {
  visible: boolean
  onClose: () => void
  opportunityId: number
}) {
  return (
    <Sheet visible={visible} onClose={onClose} title="Log activity">
      {visible ? <Body onClose={onClose} opportunityId={opportunityId} /> : null}
    </Sheet>
  )
}

function Body({ onClose, opportunityId }: { onClose: () => void; opportunityId: number }) {
  const create = useCreateInteraction()
  const [error, setError] = useState<string | null>(null)
  const { control, handleSubmit } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { type: "call", direction: "out", summary: "" },
  })
  const submit = handleSubmit(async (values) => {
    setError(null)
    try {
      await create.mutateAsync({
        opportunity_id: opportunityId,
        type: values.type,
        direction: values.direction,
        summary: values.summary.trim() === "" ? null : values.summary.trim(),
      })
      toast.success("Activity logged")
      onClose()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save. Please try again.")
    }
  })
  return (
    <>
      {error ? <FormAlert message={error} /> : null}
      <FormSelect control={control} name="type" label="Type" options={TYPE_OPTIONS} />
      <FormSelect control={control} name="direction" label="Direction" options={DIRECTION_OPTIONS} />
      <FormText control={control} name="summary" label="What happened?" multiline />
      <Button label="Save" loading={create.isPending} onPress={() => void submit()} />
    </>
  )
}
