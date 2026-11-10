import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { useCreateFollowup } from "@/api/followups"
import { FOLLOWUP_CHANNELS } from "@/api/types"
import { Field, SelectField } from "@/components/form/field"
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
import { Textarea } from "@/components/ui/textarea"
import { titleCase } from "@/lib/format"

const schema = z.object({
  due_date: z.string().min(1, "Pick a due date"),
  channel: z.enum(FOLLOWUP_CHANNELS),
  message_draft: z.string().max(2000),
})
type Values = z.infer<typeof schema>

const CHANNEL_OPTIONS = FOLLOWUP_CHANNELS.map((value) => ({ value, label: titleCase(value) }))
const DEFAULTS: Values = { due_date: "", channel: "email", message_draft: "" }

interface AddFollowupDialogProps {
  opportunityId: number
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AddFollowupDialog({ opportunityId, open, onOpenChange }: AddFollowupDialogProps) {
  const create = useCreateFollowup()
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: DEFAULTS })

  useEffect(() => {
    if (open) reset(DEFAULTS)
  }, [open, reset])

  const onSubmit = handleSubmit((values) => {
    create.mutate(
      {
        opportunity_id: opportunityId,
        due_date: values.due_date,
        channel: values.channel,
        message_draft: values.message_draft.trim() === "" ? null : values.message_draft.trim(),
      },
      {
        onSuccess: () => {
          onOpenChange(false)
          toast.success("Follow-up added")
        },
        onError: (error) => toast.error("Could not add follow-up", { description: error.message }),
      },
    )
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={(event) => void onSubmit(event)} className="space-y-5" noValidate>
          <DialogHeader>
            <DialogTitle>Add follow-up</DialogTitle>
            <DialogDescription>It will appear on Today once it is due.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Due date" error={errors.due_date?.message}>
              {(a11y) => <Input {...a11y} {...register("due_date")} type="date" className="font-mono" autoFocus />}
            </Field>
            <SelectField control={control} name="channel" label="Channel" options={CHANNEL_OPTIONS} />
          </div>
          <Field label="Message draft" error={errors.message_draft?.message}>
            {(a11y) => <Textarea {...a11y} {...register("message_draft")} rows={4} />}
          </Field>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Saving…" : "Add follow-up"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
