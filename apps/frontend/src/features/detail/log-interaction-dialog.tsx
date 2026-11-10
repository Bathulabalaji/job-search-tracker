import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { useCreateInteraction } from "@/api/interactions"
import { useOpportunities } from "@/api/opportunities"
import { DIRECTIONS, LOGGABLE_INTERACTION_TYPES } from "@/api/types"
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
  opportunity_id: z.string().min(1, "Pick an opportunity"),
  type: z.enum(LOGGABLE_INTERACTION_TYPES),
  direction: z.enum(DIRECTIONS),
  summary: z.string().max(2000),
  occurred_at: z.string(), // datetime-local; empty = now
})
type Values = z.infer<typeof schema>

const TYPE_OPTIONS = LOGGABLE_INTERACTION_TYPES.map((value) => ({ value, label: titleCase(value) }))
const DIRECTION_OPTIONS = [
  { value: "out", label: "Outgoing (I reached out)" },
  { value: "in", label: "Incoming (they reached out)" },
] as const

interface LogInteractionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** When set, the opportunity picker is hidden. */
  opportunityId?: number | undefined
}

export function LogInteractionDialog({
  open,
  onOpenChange,
  opportunityId,
}: LogInteractionDialogProps) {
  const create = useCreateInteraction()
  const opportunities = useOpportunities({}, open && opportunityId === undefined)
  const defaults: Values = {
    opportunity_id: opportunityId === undefined ? "" : String(opportunityId),
    type: "call",
    direction: "out",
    summary: "",
    occurred_at: "",
  }
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults })

  useEffect(() => {
    if (open) {
      reset({
        opportunity_id: opportunityId === undefined ? "" : String(opportunityId),
        type: "call",
        direction: "out",
        summary: "",
        occurred_at: "",
      })
    }
  }, [open, opportunityId, reset])

  const onSubmit = handleSubmit((values) => {
    create.mutate(
      {
        opportunity_id: Number(values.opportunity_id),
        type: values.type,
        direction: values.direction,
        summary: values.summary.trim() === "" ? null : values.summary.trim(),
        occurred_at: values.occurred_at === "" ? null : new Date(values.occurred_at).toISOString(),
      },
      {
        onSuccess: () => {
          onOpenChange(false)
          toast.success("Interaction logged")
        },
        onError: (error) =>
          toast.error("Could not log interaction", { description: error.message }),
      },
    )
  })

  const opportunityOptions = (opportunities.data ?? []).map((o) => ({
    value: String(o.id),
    label: `${o.company} · ${o.role}`,
  }))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={(event) => void onSubmit(event)} className="space-y-5" noValidate>
          <DialogHeader>
            <DialogTitle>Log interaction</DialogTitle>
            <DialogDescription>
              Calls, emails, messages and interviews reset the days-since-contact clock.
            </DialogDescription>
          </DialogHeader>

          {opportunityId === undefined ? (
            <SelectField
              control={control}
              name="opportunity_id"
              label="Opportunity"
              options={opportunityOptions}
              error={errors.opportunity_id?.message}
            />
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField control={control} name="type" label="Type" options={TYPE_OPTIONS} />
            <SelectField
              control={control}
              name="direction"
              label="Direction"
              options={DIRECTION_OPTIONS}
            />
          </div>
          <Field label="Summary" error={errors.summary?.message}>
            {(a11y) => <Textarea {...a11y} {...register("summary")} rows={3} autoFocus />}
          </Field>
          <Field label="When" hint="Leave empty for now" error={errors.occurred_at?.message}>
            {(a11y) => (
              <Input
                {...a11y}
                {...register("occurred_at")}
                type="datetime-local"
                className="font-mono"
              />
            )}
          </Field>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Saving…" : "Log interaction"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
