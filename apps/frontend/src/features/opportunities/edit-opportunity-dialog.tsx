import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

import { useUpdateOpportunity } from "@/api/opportunities"
import type { Opportunity } from "@/api/types"
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
  opportunitySchema,
  toUpdatePayload,
  valuesFromOpportunity,
  type OpportunityFormValues,
} from "./opportunity-form"
import { OpportunityFields } from "./opportunity-fields"

interface EditOpportunityDialogProps {
  opportunity: Opportunity
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EditOpportunityDialog({
  opportunity,
  open,
  onOpenChange,
}: EditOpportunityDialogProps) {
  const update = useUpdateOpportunity(opportunity.id)
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<OpportunityFormValues>({
    resolver: zodResolver(opportunitySchema),
    defaultValues: valuesFromOpportunity(opportunity),
  })

  useEffect(() => {
    if (open) reset(valuesFromOpportunity(opportunity))
  }, [open, opportunity, reset])

  const onSubmit = handleSubmit((values) => {
    update.mutate(toUpdatePayload(values), {
      onSuccess: () => {
        onOpenChange(false)
        toast.success("Saved")
      },
      onError: (error) => toast.error("Could not save", { description: error.message }),
    })
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <form onSubmit={(event) => void onSubmit(event)} className="space-y-6" noValidate>
          <DialogHeader>
            <DialogTitle>Edit opportunity</DialogTitle>
            <DialogDescription>
              Change the stage from the board or the detail header so follow-ups stay in sync.
            </DialogDescription>
          </DialogHeader>
          <OpportunityFields control={control} register={register} errors={errors} full />
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
