import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { BadgeCheck, KeyRound, LogOut, ShieldCheck, UserRound } from "lucide-react"
import { useState } from "react"
import { useForm, useWatch } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { authApi } from "@/api/auth"
import { ApiError, retryMessage } from "@/api/client"
import { FormAlert } from "@/components/auth/form-alert"
import { PasswordInput } from "@/components/auth/password-input"
import { PasswordStrength } from "@/components/auth/password-strength"
import { PageHeader } from "@/components/common/page-header"
import { Field } from "@/components/form/field"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useAuth, useCurrentUser } from "@/features/auth/auth-context"
import { passwordProblem } from "@/features/auth/password-policy"
import { formatDate } from "@/lib/format"

const profileSchema = z.object({
  full_name: z.string().trim().min(1, "Enter your full name").max(100, "Name is too long"),
})
type ProfileValues = z.infer<typeof profileSchema>

function ProfileCard() {
  const user = useCurrentUser()
  const { setUser } = useAuth()
  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
    reset,
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { full_name: user.full_name },
  })

  const update = useMutation({
    mutationFn: authApi.updateProfile,
    onSuccess: (updated) => {
      setUser(updated)
      reset({ full_name: updated.full_name })
      toast.success("Profile updated")
    },
    onError: (error: Error) =>
      toast.error("Could not update profile", {
        description: error instanceof ApiError ? error.message : undefined,
      }),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UserRound className="size-4 text-primary" aria-hidden />
          Profile
        </CardTitle>
        <CardDescription>How you appear in the app.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={(event) =>
            void handleSubmit((v) => update.mutate({ full_name: v.full_name }))(event)
          }
          noValidate
          className="space-y-4"
        >
          <Field label="Full name" error={errors.full_name?.message}>
            {(a11y) => <Input {...a11y} {...register("full_name")} autoComplete="name" />}
          </Field>
          <Field label="Email" hint="Your email is your sign-in name and cannot be changed here.">
            {(a11y) => <Input {...a11y} value={user.email} readOnly />}
          </Field>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {user.email_verified ? (
              <Badge variant="secondary" className="gap-1">
                <BadgeCheck className="size-3" aria-hidden />
                Email verified
              </Badge>
            ) : null}
            {user.google_linked ? <Badge variant="secondary">Google sign-in linked</Badge> : null}
            <span className="font-mono text-xs text-muted-foreground">
              Member since {formatDate(user.created_at.slice(0, 10))}
            </span>
          </div>
          <Button type="submit" disabled={!isDirty || update.isPending}>
            {update.isPending ? "Saving…" : "Save changes"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password"),
    new_password: z.string().min(1, "Choose a new password"),
    confirm_password: z.string().min(1, "Confirm your new password"),
  })
  .superRefine((values, ctx) => {
    const problem = values.new_password ? passwordProblem(values.new_password) : null
    if (problem) ctx.addIssue({ code: "custom", path: ["new_password"], message: problem })
    if (values.confirm_password && values.new_password !== values.confirm_password) {
      ctx.addIssue({
        code: "custom",
        path: ["confirm_password"],
        message: "Passwords do not match",
      })
    }
  })
type PasswordValues = z.infer<typeof passwordSchema>

function SetPasswordByEmail() {
  const user = useCurrentUser()
  const send = useMutation({
    mutationFn: () => authApi.forgotPassword(user.email),
    onSuccess: () => toast.success("Check your email for a link to set a password."),
    onError: (error: Error) =>
      toast.error(error instanceof ApiError ? retryMessage(error) : "Could not send the email."),
  })
  return (
    <div className="space-y-3">
      <FormAlert tone="info">
        You sign in with Google, so this account has no password yet. You can add one by email.
      </FormAlert>
      <Button variant="outline" disabled={send.isPending} onClick={() => send.mutate()}>
        {send.isPending ? "Sending…" : "Email me a link to set a password"}
      </Button>
    </div>
  )
}

function ChangePasswordForm() {
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    control,
    reset,
    setError,
    formState: { errors },
  } = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  })

  const watched = useWatch({ control, name: "new_password" })

  const change = useMutation({
    mutationFn: authApi.changePassword,
    onSuccess: () => {
      reset()
      toast.success("Password changed", { description: "Other devices were signed out." })
    },
    onError: (error: Error) => {
      if (error instanceof ApiError && error.code === "incorrect_password") {
        setError("current_password", { message: error.message })
      } else if (
        error instanceof ApiError &&
        (error.code === "weak_password" || error.code === "password_reused")
      ) {
        setError("new_password", { message: error.message })
      } else {
        setServerError(
          error instanceof ApiError
            ? retryMessage(error)
            : "Something went wrong. Please try again.",
        )
      }
    },
  })

  const onSubmit = handleSubmit((values) => {
    setServerError(null)
    change.mutate({ current_password: values.current_password, new_password: values.new_password })
  })

  return (
    <form onSubmit={(event) => void onSubmit(event)} noValidate className="space-y-4">
      {serverError ? <FormAlert tone="error">{serverError}</FormAlert> : null}
      <Field label="Current password" error={errors.current_password?.message}>
        {(a11y) => (
          <PasswordInput
            {...a11y}
            {...register("current_password")}
            autoComplete="current-password"
          />
        )}
      </Field>
      <div className="space-y-2">
        <Field label="New password" error={errors.new_password?.message}>
          {(a11y) => (
            <PasswordInput {...a11y} {...register("new_password")} autoComplete="new-password" />
          )}
        </Field>
        <PasswordStrength password={watched} />
      </div>
      <Field label="Confirm new password" error={errors.confirm_password?.message}>
        {(a11y) => (
          <PasswordInput {...a11y} {...register("confirm_password")} autoComplete="new-password" />
        )}
      </Field>
      <Button type="submit" disabled={change.isPending}>
        {change.isPending ? "Updating…" : "Change password"}
      </Button>
    </form>
  )
}

function SecurityCard() {
  const user = useCurrentUser()
  const { signOut } = useAuth()
  const everywhere = useMutation({
    mutationFn: authApi.logoutEverywhere,
    onSettled: () => void signOut(),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4 text-primary" aria-hidden />
          Password
        </CardTitle>
        <CardDescription>
          Changing your password signs you out of every other device.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {user.has_password ? <ChangePasswordForm /> : <SetPasswordByEmail />}
        <div className="space-y-3 border-t pt-5">
          <div className="flex items-center gap-2 text-sm font-medium">
            <ShieldCheck className="size-4 text-primary" aria-hidden />
            Sessions
          </div>
          <p className="text-sm text-muted-foreground">
            Lost a device or used a shared computer? Sign out everywhere, including here.
          </p>
          <Button
            variant="outline"
            disabled={everywhere.isPending}
            onClick={() => everywhere.mutate()}
          >
            <LogOut />
            {everywhere.isPending ? "Signing out…" : "Sign out of all devices"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function AccountPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Account" description="Your profile and sign-in security." />
      <div className="space-y-6">
        <ProfileCard />
        <SecurityCard />
      </div>
    </div>
  )
}
