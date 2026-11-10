import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { useCreatePrepItem, useUpdatePrepItem } from "@/api/prep-items"
import { PREP_CATEGORIES, PREP_STATUSES, type PrepItem } from "@/api/types"
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
import { CATEGORY_LABELS } from "./categories"

const schema = z.object({
  topic: z.string().trim().min(1, "Topic is required").max(300),
  category: z.enum(PREP_CATEGORIES),
  status: z.enum(PREP_STATUSES),
  confidence: z.enum(["1", "2", "3", "4", "5"]),
  notes: z.string().max(4000),
})
type Values = z.infer<typeof schema>

const CATEGORY_OPTIONS = PREP_CATEGORIES.map((value) => ({ value, label: CATEGORY_LABELS[value] }))
const STATUS_OPTIONS = PREP_STATUSES.map((value) => ({ value, label: titleCase(value) }))
const CONFIDENCE_OPTIONS = [
  { value: "1", label: "1 · Not confident" },
  { value: "2", label: "2 · Shaky" },
  { value: "3", label: "3 · Okay" },
  { value: "4", label: "4 · Confident" },
  { value: "5", label: "5 · Very confident" },
] as const

function valuesFor(item: PrepItem | null, category: PrepItem["category"]): Values {
  return {
    topic: item?.topic ?? "",
    category: item?.category ?? category,
    status: item?.status ?? "todo",
    confidence: String(item?.confidence ?? 1) as Values["confidence"],
    notes: item?.notes ?? "",
  }
}

interface PrepItemDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Null = add a new topic. */
  item: PrepItem | null
  defaultCategory: PrepItem["category"]
}

export function PrepItemDialog({ open, onOpenChange, item, defaultCategory }: PrepItemDialogProps) {
  const create = useCreatePrepItem()
  const update = useUpdatePrepItem()
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: valuesFor(item, defaultCategory),
  })

  useEffect(() => {
    if (open) reset(valuesFor(item, defaultCategory))
  }, [open, item, defaultCategory, reset])

  const onSubmit = handleSubmit((values) => {
    const body = {
      topic: values.topic.trim(),
      category: values.category,
      status: values.status,
      confidence: Number(values.confidence),
      notes: values.notes.trim() === "" ? null : values.notes.trim(),
    }
    const finish = () => {
      onOpenChange(false)
      toast.success(item ? "Topic updated" : "Topic added")
    }
    if (item) {
      update.mutate({ id: item.id, patch: body }, { onSuccess: finish })
    } else {
      create.mutate(body, {
        onSuccess: finish,
        onError: (error) => toast.error("Could not add topic", { description: error.message }),
      })
    }
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={(event) => void onSubmit(event)} className="space-y-5" noValidate>
          <DialogHeader>
            <DialogTitle>{item ? "Edit topic" : "Add topic"}</DialogTitle>
            <DialogDescription>
              Something you want to be able to explain in an interview.
            </DialogDescription>
          </DialogHeader>
          <Field label="Topic" error={errors.topic?.message}>
            {(a11y) => <Input {...a11y} {...register("topic")} autoFocus autoComplete="off" />}
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <SelectField
              control={control}
              name="category"
              label="Category"
              options={CATEGORY_OPTIONS}
            />
            <SelectField control={control} name="status" label="Status" options={STATUS_OPTIONS} />
            <SelectField
              control={control}
              name="confidence"
              label="Confidence"
              options={CONFIDENCE_OPTIONS}
            />
          </div>
          <Field label="Notes" error={errors.notes?.message}>
            {(a11y) => <Textarea {...a11y} {...register("notes")} rows={4} />}
          </Field>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending || update.isPending}>
              {item ? "Save changes" : "Add topic"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
