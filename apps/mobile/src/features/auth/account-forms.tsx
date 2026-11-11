import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { authApi, type AuthUser } from "@/api/auth"
import { ApiError, retryMessage } from "@/api/client"
import { FormAlert } from "@/components/auth/auth-shell"
import { Button } from "@/components/ui/button"
import { FormText } from "@/components/ui/form"
import { Sheet } from "@/components/ui/sheet"
import { useAuth } from "./auth-context"
import { passwordProblem } from "./password-policy"
import { toast } from "@/lib/toast-bus"

const nameSchema = z.object({ full_name: z.string().trim().min(1, "Enter your name").max(100) })

export function EditNameSheet({ visible, onClose, user }: { visible: boolean; onClose: () => void; user: AuthUser }) {
  return (
    <Sheet visible={visible} onClose={onClose} title="Edit name">
      {visible ? <NameBody user={user} onClose={onClose} /> : null}
    </Sheet>
  )
}

function NameBody({ user, onClose }: { user: AuthUser; onClose: () => void }) {
  const { setUser } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const { control, handleSubmit } = useForm<z.infer<typeof nameSchema>>({
    resolver: zodResolver(nameSchema),
    defaultValues: { full_name: user.full_name },
  })
  const save = useMutation({
    mutationFn: authApi.updateProfile,
    onSuccess: (updated) => {
      setUser(updated)
      toast.success("Name updated")
      onClose()
    },
    onError: (e: Error) => setError(e instanceof ApiError ? e.message : "Could not save."),
  })
  return (
    <>
      {error ? <FormAlert message={error} /> : null}
      <FormText control={control} name="full_name" label="Full name" autoCapitalize="words" />
      <Button
        label="Save"
        loading={save.isPending}
        onPress={() => void handleSubmit((v) => save.mutate({ full_name: v.full_name }))()}
      />
    </>
  )
}

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password"),
    new_password: z.string().min(1, "Choose a new password"),
    confirm: z.string().min(1, "Repeat the new password"),
  })
  .superRefine((v, ctx) => {
    const problem = passwordProblem(v.new_password)
    if (problem) ctx.addIssue({ code: "custom", path: ["new_password"], message: problem })
    if (v.confirm && v.new_password !== v.confirm)
      ctx.addIssue({ code: "custom", path: ["confirm"], message: "Passwords do not match" })
  })

export function ChangePasswordSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  return (
    <Sheet visible={visible} onClose={onClose} title="Change password">
      {visible ? <PasswordBody onClose={onClose} /> : null}
    </Sheet>
  )
}

function PasswordBody({ onClose }: { onClose: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const { control, handleSubmit, setError: setFieldError } = useForm<z.infer<typeof passwordSchema>>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  })
  const change = useMutation({
    mutationFn: authApi.changePassword,
    onSuccess: () => {
      toast.success("Password changed", "Other devices were signed out.")
      onClose()
    },
    onError: (e: Error) => {
      if (e instanceof ApiError && e.code === "incorrect_password") {
        setFieldError("current_password", { message: "That password is not correct" })
      } else {
        setError(e instanceof ApiError ? retryMessage(e) : "Could not change password.")
      }
    },
  })
  return (
    <>
      {error ? <FormAlert message={error} /> : null}
      <FormText control={control} name="current_password" label="Current password" secureToggle autoCapitalize="none" textContentType="password" />
      <FormText control={control} name="new_password" label="New password" secureToggle autoCapitalize="none" textContentType="newPassword" hint="At least 10 characters with a letter and a number." />
      <FormText control={control} name="confirm" label="Confirm new password" secureToggle autoCapitalize="none" textContentType="newPassword" />
      <Button
        label="Change password"
        loading={change.isPending}
        onPress={() =>
          void handleSubmit((v) => {
            setError(null)
            change.mutate({ current_password: v.current_password, new_password: v.new_password })
          })()
        }
      />
    </>
  )
}
