import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { Alert } from "react-native"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { ApiError } from "@/api/client"
import { useCreateResume, useDeleteResume, useUpdateResume } from "@/api/resumes"
import type { Resume } from "@/api/types"
import { FormAlert } from "@/components/auth/auth-shell"
import { Button } from "@/components/ui/button"
import { FormText } from "@/components/ui/form"
import { Sheet } from "@/components/ui/sheet"
import { toast } from "@/lib/toast-bus"

const schema = z.object({
  label: z.string().trim().min(1, "Label is required").max(200),
  focus: z.string().max(200),
  file_name: z
    .string()
    .max(255)
    .refine((v) => !/[\\/]/.test(v), "Enter a file name, not a path"),
  version: z.string().trim().min(1, "Version is required").max(50),
  notes: z.string().max(4000),
})
type Values = z.infer<typeof schema>
const orNull = (v: string): string | null => (v.trim() === "" ? null : v.trim())

interface Props {
  visible: boolean
  onClose: () => void
  resume: Resume | null
}

export function ResumeSheet({ visible, onClose, resume }: Props) {
  return (
    <Sheet visible={visible} onClose={onClose} title={resume ? "Edit resume" : "Add resume"}>
      {visible ? <Body onClose={onClose} resume={resume} /> : null}
    </Sheet>
  )
}

function Body({ onClose, resume }: Omit<Props, "visible">) {
  const create = useCreateResume()
  const update = useUpdateResume()
  const remove = useDeleteResume()
  const [error, setError] = useState<string | null>(null)
  const { control, handleSubmit } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      label: resume?.label ?? "",
      focus: resume?.focus ?? "",
      file_name: resume?.file_name ?? "",
      version: resume?.version ?? "1.0",
      notes: resume?.notes ?? "",
    },
  })
  const submit = handleSubmit(async (v) => {
    setError(null)
    const payload = {
      label: v.label.trim(),
      focus: orNull(v.focus),
      file_name: orNull(v.file_name),
      version: v.version.trim(),
      notes: orNull(v.notes),
    }
    try {
      if (resume) await update.mutateAsync({ id: resume.id, patch: payload })
      else await create.mutateAsync(payload)
      toast.success(resume ? "Saved" : "Resume added")
      onClose()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save. Please try again.")
    }
  })
  return (
    <>
      {error ? <FormAlert message={error} /> : null}
      <FormText control={control} name="label" label="Label" />
      <FormText control={control} name="focus" label="Focus" hint="e.g. Backend, Full-stack" />
      <FormText control={control} name="file_name" label="File name" autoCapitalize="none" autoCorrect={false} hint="Just the name. Files are not uploaded." />
      <FormText control={control} name="version" label="Version" autoCapitalize="none" />
      <FormText control={control} name="notes" label="Notes" multiline />
      <Button label="Save" loading={create.isPending || update.isPending} onPress={() => void submit()} />
      {resume ? (
        <Button
          label="Delete resume"
          icon="trash-outline"
          variant="danger"
          onPress={() =>
            Alert.alert(`Delete "${resume.label}"?`, undefined, [
              { text: "Cancel", style: "cancel" },
              {
                text: "Delete",
                style: "destructive",
                onPress: () =>
                  remove.mutate(resume.id, {
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
