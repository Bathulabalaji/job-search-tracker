import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { Alert } from "react-native"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { ApiError } from "@/api/client"
import { useCreatePrepItem, useDeletePrepItem, useUpdatePrepItem } from "@/api/prep-items"
import { PREP_CATEGORIES, PREP_STATUSES, type PrepItem } from "@/api/types"
import { FormAlert } from "@/components/auth/auth-shell"
import { Button } from "@/components/ui/button"
import { FormSelect, FormText } from "@/components/ui/form"
import { Sheet } from "@/components/ui/sheet"
import { titleCase } from "@/lib/format"
import { toast } from "@/lib/toast-bus"
import { CATEGORY_LABELS } from "./categories"

const schema = z.object({
  topic: z.string().trim().min(1, "Topic is required").max(200),
  category: z.enum(PREP_CATEGORIES),
  status: z.enum(PREP_STATUSES),
  confidence: z.number().int().min(1).max(5),
  notes: z.string().max(4000),
})
type Values = z.infer<typeof schema>

const CATEGORY_OPTIONS = PREP_CATEGORIES.map((value) => ({ value, label: CATEGORY_LABELS[value] }))
const STATUS_OPTIONS = PREP_STATUSES.map((value) => ({ value, label: titleCase(value) }))
const CONFIDENCE_OPTIONS = [1, 2, 3, 4, 5].map((value) => ({
  value,
  label: `${value} · ${["Very low", "Low", "Okay", "Good", "Strong"][value - 1]}`,
}))

interface Props {
  visible: boolean
  onClose: () => void
  item: PrepItem | null
}

export function PrepSheet({ visible, onClose, item }: Props) {
  return (
    <Sheet visible={visible} onClose={onClose} title={item ? "Edit topic" : "Add topic"}>
      {visible ? <Body onClose={onClose} item={item} /> : null}
    </Sheet>
  )
}

function Body({ onClose, item }: Omit<Props, "visible">) {
  const create = useCreatePrepItem()
  const update = useUpdatePrepItem()
  const remove = useDeletePrepItem()
  const [error, setError] = useState<string | null>(null)
  const { control, handleSubmit } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      topic: item?.topic ?? "",
      category: item?.category ?? "python",
      status: item?.status ?? "todo",
      confidence: item?.confidence ?? 3,
      notes: item?.notes ?? "",
    },
  })

  const submit = handleSubmit(async (v) => {
    setError(null)
    const payload = {
      topic: v.topic.trim(),
      category: v.category,
      status: v.status,
      confidence: v.confidence,
      notes: v.notes.trim() === "" ? null : v.notes.trim(),
    }
    try {
      if (item) await update.mutateAsync({ id: item.id, patch: payload })
      else await create.mutateAsync(payload)
      toast.success(item ? "Saved" : "Topic added")
      onClose()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save. Please try again.")
    }
  })

  return (
    <>
      {error ? <FormAlert message={error} /> : null}
      <FormText control={control} name="topic" label="Topic" />
      <FormSelect control={control} name="category" label="Category" options={CATEGORY_OPTIONS} />
      <FormSelect control={control} name="status" label="Status" options={STATUS_OPTIONS} />
      <FormSelect control={control} name="confidence" label="Confidence" options={CONFIDENCE_OPTIONS} />
      <FormText control={control} name="notes" label="Notes" multiline />
      <Button label="Save" loading={create.isPending || update.isPending} onPress={() => void submit()} />
      {item ? (
        <Button
          label="Delete topic"
          icon="trash-outline"
          variant="danger"
          onPress={() =>
            Alert.alert(`Delete "${item.topic}"?`, undefined, [
              { text: "Cancel", style: "cancel" },
              {
                text: "Delete",
                style: "destructive",
                onPress: () =>
                  remove.mutate(item.id, {
                    onSuccess: () => {
                      toast.success("Deleted")
                      onClose()
                    },
                  }),
              },
            ])
          }
        />
      ) : null}
    </>
  )
}
