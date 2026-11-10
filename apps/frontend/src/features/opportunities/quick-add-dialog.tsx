import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { useCreateOpportunity } from "@/api/opportunities"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DEFAULT_VALUES,
  opportunitySchema,
  toCreatePayload,
  type OpportunityFormValues,
} from "./opportunity-form"
import { OpportunityFields } from "./opportunity-fields"

interface QuickAddDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function QuickAddDialog({ open, onOpenChange }: QuickAddDialogProps) {
  const navigate = useNavigate()
  const create = useCreateOpportunity()
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<OpportunityFormValues>({
    resolver: zodResolver(opportunitySchema),
    defaultValues: DEFAULT_VALUES,
  })

  useEffect(() => {
    if (open) reset(DEFAULT_VALUES)
  }, [open, reset])

  const onSubmit = handleSubmit((values) => {
    create.mutate(toCreatePayload(values), {
      onSuccess: (created) => {
        onOpenChange(false)
        toast.success(`Added ${created.company}`, {
          description: created.role,
          action: { label: "Open", onClick: () => void navigate(`/opportunities/${created.id}`) },
        })
      },
      onError: (error) => toast.error("Could not add opportunity", { description: error.message }),
    })
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <form onSubmit={(event) => void onSubmit(event)} className="space-y-6" noValidate>
          <DialogHeader>
            <DialogTitle>Add opportunity</DialogTitle>
            <DialogDescription>
              Just the essentials. Add the JD, tags and next action from the detail page.
            </DialogDescription>
          </DialogHeader>
          <OpportunityFields control={control} register={register} errors={errors} full={false} />
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Adding…" : "Add opportunity"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
