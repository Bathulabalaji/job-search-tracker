import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { useCreateResume, useUpdateResume } from "@/api/resumes"
import type { Resume } from "@/api/types"
import { Field } from "@/components/form/field"
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

function valuesFor(resume: Resume | null): Values {
  return {
    label: resume?.label ?? "",
    focus: resume?.focus ?? "",
    file_name: resume?.file_name ?? "",
    version: resume?.version ?? "1",
    notes: resume?.notes ?? "",
  }
}

interface ResumeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Null = add a new resume. */
  resume: Resume | null
}

export function ResumeDialog({ open, onOpenChange, resume }: ResumeDialogProps) {
  const create = useCreateResume()
  const update = useUpdateResume()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: valuesFor(resume) })

  useEffect(() => {
    if (open) reset(valuesFor(resume))
  }, [open, resume, reset])

  const onSubmit = handleSubmit((values) => {
    const body = {
      label: values.label.trim(),
      focus: orNull(values.focus),
      file_name: orNull(values.file_name),
      version: values.version.trim(),
      notes: orNull(values.notes),
    }
    const finish = () => {
      onOpenChange(false)
      toast.success(resume ? "Resume updated" : "Resume added")
    }
    const failed = (error: Error) =>
      toast.error("Could not save resume", { description: error.message })
    if (resume) {
      update.mutate({ id: resume.id, patch: body }, { onSuccess: finish, onError: failed })
    } else {
      create.mutate(body, { onSuccess: finish, onError: failed })
    }
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={(event) => void onSubmit(event)} className="space-y-5" noValidate>
          <DialogHeader>
            <DialogTitle>{resume ? "Edit resume" : "Add resume"}</DialogTitle>
            <DialogDescription>
              Track which version you send where. Only details are saved here, never the file
              itself.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Label" error={errors.label?.message}>
              {(a11y) => (
                <Input
                  {...a11y}
                  {...register("label")}
                  placeholder="Backend (Python)"
                  autoFocus
                  autoComplete="off"
                />
              )}
            </Field>
            <Field label="Version" error={errors.version?.message}>
              {(a11y) => <Input {...a11y} {...register("version")} className="font-mono" />}
            </Field>
          </div>
          <Field label="Focus" hint="What this version emphasises" error={errors.focus?.message}>
            {(a11y) => <Input {...a11y} {...register("focus")} placeholder="FastAPI, PostgreSQL" />}
          </Field>
          <Field
            label="File name"
            hint="Just the name, for example resume_backend_v3.pdf"
            error={errors.file_name?.message}
          >
            {(a11y) => <Input {...a11y} {...register("file_name")} className="font-mono" />}
          </Field>
          <Field label="Notes" error={errors.notes?.message}>
            {(a11y) => <Textarea {...a11y} {...register("notes")} rows={3} />}
          </Field>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending || update.isPending}>
              {create.isPending || update.isPending
                ? "Saving…"
                : resume
                  ? "Save changes"
                  : "Add resume"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
