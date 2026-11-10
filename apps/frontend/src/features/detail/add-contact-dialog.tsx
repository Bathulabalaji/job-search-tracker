import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { useCreateContact } from "@/api/contacts"
import { CONTACT_ROLES } from "@/api/types"
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
  name: z.string().trim().min(1, "Name is required").max(200),
  role: z.enum(CONTACT_ROLES),
  company: z.string().max(200),
  email: z.string().max(254).refine((v) => v === "" || /^\S+@\S+\.\S+$/.test(v), "Enter a valid email"),
  phone: z.string().max(50),
  linkedin_url: z.string().max(1000),
  notes: z.string(),
})
type Values = z.infer<typeof schema>

const ROLE_OPTIONS = CONTACT_ROLES.map((value) => ({ value, label: titleCase(value) }))
const orNull = (v: string): string | null => (v.trim() === "" ? null : v.trim())

interface AddContactDialogProps {
  opportunityId: number
  defaultCompany: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AddContactDialog({ opportunityId, defaultCompany, open, onOpenChange }: AddContactDialogProps) {
  const create = useCreateContact()
  const defaults: Values = {
    name: "",
    role: "recruiter",
    company: defaultCompany,
    email: "",
    phone: "",
    linkedin_url: "",
    notes: "",
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
      reset({ name: "", role: "recruiter", company: defaultCompany, email: "", phone: "", linkedin_url: "", notes: "" })
    }
  }, [open, defaultCompany, reset])

  const onSubmit = handleSubmit((values) => {
    create.mutate(
      {
        opportunity_id: opportunityId,
        name: values.name.trim(),
        role: values.role,
        company: orNull(values.company),
        email: orNull(values.email),
        phone: orNull(values.phone),
        linkedin_url: orNull(values.linkedin_url),
        notes: orNull(values.notes),
      },
      {
        onSuccess: () => {
          onOpenChange(false)
          toast.success("Contact added")
        },
        onError: (error) => toast.error("Could not add contact", { description: error.message }),
      },
    )
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <form onSubmit={(event) => void onSubmit(event)} className="space-y-5" noValidate>
          <DialogHeader>
            <DialogTitle>Add contact</DialogTitle>
            <DialogDescription>
              Recruiters, HR, managers and referrers. Don&apos;t store IDs, passwords or bank details here.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name" error={errors.name?.message}>
              {(a11y) => <Input {...a11y} {...register("name")} autoFocus autoComplete="off" />}
            </Field>
            <SelectField control={control} name="role" label="Role" options={ROLE_OPTIONS} />
            <Field label="Company" error={errors.company?.message}>
              {(a11y) => <Input {...a11y} {...register("company")} />}
            </Field>
            <Field label="Email" error={errors.email?.message}>
              {(a11y) => <Input {...a11y} {...register("email")} type="email" />}
            </Field>
            <Field label="Phone" error={errors.phone?.message}>
              {(a11y) => <Input {...a11y} {...register("phone")} type="tel" className="font-mono" />}
            </Field>
            <Field label="LinkedIn URL" error={errors.linkedin_url?.message}>
              {(a11y) => <Input {...a11y} {...register("linkedin_url")} inputMode="url" />}
            </Field>
          </div>
          <Field label="Notes" error={errors.notes?.message}>
            {(a11y) => <Textarea {...a11y} {...register("notes")} rows={3} />}
          </Field>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Saving…" : "Add contact"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
