import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { ApiError } from "@/api/client"
import { useCreateContact, useUpdateContact } from "@/api/contacts"
import { CONTACT_ROLES, type Contact } from "@/api/types"
import { FormAlert } from "@/components/auth/auth-shell"
import { Button } from "@/components/ui/button"
import { FormSelect, FormText } from "@/components/ui/form"
import { Sheet } from "@/components/ui/sheet"
import { titleCase } from "@/lib/format"
import { toast } from "@/lib/toast-bus"

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
  notes: z.string(),
})
type Values = z.infer<typeof schema>

const ROLE_OPTIONS = CONTACT_ROLES.map((value) => ({ value, label: titleCase(value) }))
const orNull = (v: string): string | null => (v.trim() === "" ? null : v.trim())

interface Props {
  visible: boolean
  onClose: () => void
  /** null = add a new contact. */
  contact?: Contact | null
  /** Pins a new contact to an opportunity (detail screen). */
  opportunityId?: number
  defaultCompany?: string
}

export function ContactSheet({ visible, onClose, ...rest }: Props) {
  return (
    <Sheet visible={visible} onClose={onClose} title={rest.contact ? "Edit contact" : "Add contact"}>
      {visible ? <Body onClose={onClose} {...rest} /> : null}
    </Sheet>
  )
}

function Body({
  onClose,
  contact = null,
  opportunityId,
  defaultCompany = "",
}: Omit<Props, "visible">) {
  const create = useCreateContact()
  const update = useUpdateContact()
  const [error, setError] = useState<string | null>(null)
  const { control, handleSubmit } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: contact?.name ?? "",
      role: contact?.role ?? "recruiter",
      company: contact?.company ?? defaultCompany,
      email: contact?.email ?? "",
      phone: contact?.phone ?? "",
      linkedin_url: contact?.linkedin_url ?? "",
      notes: contact?.notes ?? "",
    },
  })
  const submit = handleSubmit(async (v) => {
    setError(null)
    const payload = {
      opportunity_id: contact ? contact.opportunity_id : (opportunityId ?? null),
      name: v.name.trim(),
      role: v.role,
      company: orNull(v.company),
      email: orNull(v.email),
      phone: orNull(v.phone),
      linkedin_url: orNull(v.linkedin_url),
      notes: orNull(v.notes),
    }
    try {
      if (contact) await update.mutateAsync({ id: contact.id, patch: payload })
      else await create.mutateAsync(payload)
      toast.success(contact ? "Contact saved" : "Contact added")
      onClose()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save. Please try again.")
    }
  })
  return (
    <>
      {error ? <FormAlert message={error} /> : null}
      <FormText control={control} name="name" label="Name" autoCapitalize="words" />
      <FormSelect control={control} name="role" label="Role" options={ROLE_OPTIONS} />
      <FormText control={control} name="company" label="Company" />
      <FormText control={control} name="email" label="Email" keyboardType="email-address" autoCapitalize="none" autoCorrect={false} />
      <FormText control={control} name="phone" label="Phone" keyboardType="phone-pad" />
      <FormText control={control} name="linkedin_url" label="LinkedIn URL" autoCapitalize="none" keyboardType="url" autoCorrect={false} />
      <FormText control={control} name="notes" label="Notes" multiline />
      <Button label="Save" loading={create.isPending || update.isPending} onPress={() => void submit()} />
    </>
  )
}
