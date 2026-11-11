import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { ApiError } from "@/api/client"
import { useCreateFollowup } from "@/api/followups"
import { FOLLOWUP_CHANNELS } from "@/api/types"
import { FormAlert } from "@/components/auth/auth-shell"
import { Button } from "@/components/ui/button"
import { FormDate, FormSelect, FormText } from "@/components/ui/form"
import { Sheet } from "@/components/ui/sheet"
import { isIsoDate, todayIso } from "@/lib/dates"
import { addDays, titleCase } from "@/lib/format"
import { toast } from "@/lib/toast-bus"

const schema = z.object({
  due_date: z.string().refine(isIsoDate, "Pick a valid date"),
  channel: z.enum(FOLLOWUP_CHANNELS),
  message_draft: z.string().max(2000),
})
type Values = z.infer<typeof schema>

const CHANNEL_OPTIONS = FOLLOWUP_CHANNELS.map((value) => ({ value, label: titleCase(value) }))

export function FollowupSheet({
  visible,
  onClose,
  opportunityId,
}: {
  visible: boolean
  onClose: () => void
  opportunityId: number
}) {
  return (
    <Sheet visible={visible} onClose={onClose} title="Add follow-up">
      {visible ? <Body onClose={onClose} opportunityId={opportunityId} /> : null}
    </Sheet>
  )
}

function Body({ onClose, opportunityId }: { onClose: () => void; opportunityId: number }) {
  const create = useCreateFollowup()
  const [error, setError] = useState<string | null>(null)
  const { control, handleSubmit } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { due_date: addDays(todayIso(), 2), channel: "email", message_draft: "" },
  })
  const submit = handleSubmit(async (values) => {
    setError(null)
    try {
      await create.mutateAsync({
        opportunity_id: opportunityId,
        due_date: values.due_date,
        channel: values.channel,
        message_draft: values.message_draft.trim() === "" ? null : values.message_draft.trim(),
      })
      toast.success("Follow-up added")
      onClose()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save. Please try again.")
    }
  })
  return (
    <>
      {error ? <FormAlert message={error} /> : null}
      <FormDate control={control} name="due_date" label="Due date" />
      <FormSelect control={control} name="channel" label="Channel" options={CHANNEL_OPTIONS} />
      <FormText control={control} name="message_draft" label="Message draft (optional)" multiline />
      <Button label="Add follow-up" loading={create.isPending} onPress={() => void submit()} />
    </>
  )
}
