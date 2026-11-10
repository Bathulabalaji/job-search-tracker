import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { useCreateContact, useUpdateContact } from "@/api/contacts"
import { useOpportunities } from "@/api/opportunities"
import { CONTACT_ROLES, type Contact } from "@/api/types"
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

const NO_OPPORTUNITY = "none"

const schema = z.object({
  name: z.string().trim().min(1, "Name is required").max(200),
  role: z.enum(CONTACT_ROLES),
  company: z.string().max(200),
  email: z
    .string()
    .max(254)
    .refine((v) => v === "" || /^\S+@\S+\.\S+$/.test(v), "Enter a valid email"),
  phone: z.string().max(50),
  linkedin_url: z.string().max(1000),
  opportunity_id: z.string(),
  notes: z.string(),
})
type Values = z.infer<typeof schema>

const ROLE_OPTIONS = CONTACT_ROLES.map((value) => ({ value, label: titleCase(value) }))
const orNull = (v: string): string | null => (v.trim() === "" ? null : v.trim())

function valuesFor(
  contact: Contact | null,
  fixedOpportunityId: number | undefined,
  defaultCompany: string,
): Values {
  const linked = fixedOpportunityId ?? contact?.opportunity_id ?? null
  return {
    name: contact?.name ?? "",
    role: contact?.role ?? "recruiter",
    company: contact?.company ?? defaultCompany,
    email: contact?.email ?? "",
    phone: contact?.phone ?? "",
    linkedin_url: contact?.linkedin_url ?? "",
    opportunity_id: linked === null ? NO_OPPORTUNITY : String(linked),
    notes: contact?.notes ?? "",
  }
}

interface ContactDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Null = add a new contact. */
  contact?: Contact | null
  /** Pins the contact to one opportunity and hides the picker (detail page). */
  opportunityId?: number
  defaultCompany?: string
}

export function ContactDialog({
  open,
  onOpenChange,
  contact = null,
  opportunityId,
  defaultCompany = "",
}: ContactDialogProps) {
  const create = useCreateContact()
  const update = useUpdateContact()
  const opportunities = useOpportunities({}, open && opportunityId === undefined)
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: valuesFor(contact, opportunityId, defaultCompany),
  })

  useEffect(() => {
    if (open) reset(valuesFor(contact, opportunityId, defaultCompany))
  }, [open, contact, opportunityId, defaultCompany, reset])

  const opportunityOptions = [
    { value: NO_OPPORTUNITY, label: "Not linked to an opportunity" },
    ...(opportunities.data ?? []).map((o) => ({
      value: String(o.id),
      label: `${o.company} · ${o.role}`,
    })),
  ]

  const onSubmit = handleSubmit((values) => {
    const body = {
      opportunity_id:
        values.opportunity_id === NO_OPPORTUNITY ? null : Number(values.opportunity_id),
      name: values.name.trim(),
      role: values.role,
      company: orNull(values.company),
      email: orNull(values.email),
      phone: orNull(values.phone),
      linkedin_url: orNull(values.linkedin_url),
      notes: orNull(values.notes),
    }
    const finish = () => {
      onOpenChange(false)
      toast.success(contact ? "Contact updated" : "Contact added")
    }
    const failed = (error: Error) =>
      toast.error(contact ? "Could not update contact" : "Could not add contact", {
        description: error.message,
      })
    if (contact) {
      update.mutate({ id: contact.id, patch: body }, { onSuccess: finish, onError: failed })
    } else {
      create.mutate(body, { onSuccess: finish, onError: failed })
    }
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <form onSubmit={(event) => void onSubmit(event)} className="space-y-5" noValidate>
          <DialogHeader>
            <DialogTitle>{contact ? "Edit contact" : "Add contact"}</DialogTitle>
            <DialogDescription>
              Recruiters, HR, managers and referrers. Don&apos;t store IDs, passwords or bank
              details here.
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
              {(a11y) => (
                <Input {...a11y} {...register("phone")} type="tel" className="font-mono" />
              )}
            </Field>
            <Field label="LinkedIn URL" error={errors.linkedin_url?.message}>
              {(a11y) => <Input {...a11y} {...register("linkedin_url")} inputMode="url" />}
            </Field>
          </div>
          {opportunityId === undefined ? (
            <SelectField
              control={control}
              name="opportunity_id"
              label="Opportunity"
              options={opportunityOptions}
            />
          ) : null}
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
                : contact
                  ? "Save changes"
                  : "Add contact"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
