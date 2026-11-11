import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery } from "@tanstack/react-query"
import { CheckCircle2, LinkIcon, Loader2 } from "lucide-react"
import { useState } from "react"
import { useForm, useWatch } from "react-hook-form"
import { Link } from "react-router-dom"
import { z } from "zod"

import { authApi } from "@/api/auth"
import { ApiError, retryMessage } from "@/api/client"
import { FormAlert } from "@/components/auth/form-alert"
import { PasswordInput } from "@/components/auth/password-input"
import { PasswordStrength } from "@/components/auth/password-strength"
import { Field } from "@/components/form/field"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card"
import { useHashToken } from "@/features/auth/use-hash-token"
import { passwordProblem } from "@/features/auth/password-policy"

const schema = z
  .object({
    password: z.string().min(1, "Choose a new password"),
    confirm_password: z.string().min(1, "Confirm your new password"),
  })
  .superRefine((values, ctx) => {
    const problem = values.password ? passwordProblem(values.password) : null
    if (problem) ctx.addIssue({ code: "custom", path: ["password"], message: problem })
    if (values.confirm_password && values.password !== values.confirm_password) {
      ctx.addIssue({
        code: "custom",
        path: ["confirm_password"],
        message: "Passwords do not match",
      })
    }
  })
type Values = z.infer<typeof schema>

/** Codes that mean the link itself is unusable (as opposed to a fixable password problem). */
const DEAD_LINK_CODES = new Set(["invalid_token", "token_used", "token_expired"])

function InvalidLink({ message }: { message: string }) {
  return (
    <Card>
      <CardHeader className="items-center text-center">
        <div className="mb-2 flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
          <LinkIcon className="size-6" aria-hidden />
        </div>
        <h1 className="text-xl font-semibold tracking-tight">This link cannot be used</h1>
        <CardDescription>{message}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-center">
        <Button asChild className="w-full">
          <Link to="/forgot-password">Request a new link</Link>
        </Button>
        <Link to="/login" className="inline-block text-sm font-medium text-primary hover:underline">
          Back to sign in
        </Link>
      </CardContent>
    </Card>
  )
}

export function ResetPasswordPage() {
  // The token is scrubbed from the address bar so it cannot leak via history or screenshots.
  const { token, attempt } = useHashToken()
  return <ResetPasswordContent key={attempt} token={token} />
}

function ResetPasswordContent({ token }: { token: string | null }) {
  const [deadLink, setDeadLink] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { password: "", confirm_password: "" },
  })

  const watched = useWatch({ control, name: "password" })

  // Ask the server up front, so a used or expired link says so before anyone types a password.
  const linkCheck = useQuery({
    queryKey: ["reset-link-check", token],
    queryFn: () => authApi.checkResetToken(token ?? ""),
    enabled: token !== null,
    retry: false,
    staleTime: Infinity,
  })

  const reset = useMutation({
    mutationFn: authApi.resetPassword,
    onSuccess: () => setDone(true),
    onError: (error: Error) => {
      if (error instanceof ApiError && error.code && DEAD_LINK_CODES.has(error.code)) {
        setDeadLink(error.message)
      } else if (error instanceof ApiError && error.code === "weak_password") {
        setError("password", { message: error.message })
      } else {
        setServerError(
          error instanceof ApiError
            ? retryMessage(error)
            : "Something went wrong. Please try again.",
        )
      }
    },
  })

  if (!token) {
    return <InvalidLink message="The reset link is missing or incomplete. Request a new one." />
  }
  if (deadLink) return <InvalidLink message={deadLink} />
  if (linkCheck.isPending) {
    return (
      <Card role="status" aria-live="polite">
        <CardHeader className="items-center text-center">
          <Loader2 className="mb-2 size-8 animate-spin text-primary" aria-hidden />
          <h1 className="text-xl font-semibold tracking-tight">Checking your link…</h1>
        </CardHeader>
      </Card>
    )
  }
  const checkError = linkCheck.error
  if (checkError instanceof ApiError && checkError.code && DEAD_LINK_CODES.has(checkError.code)) {
    return <InvalidLink message={checkError.message} />
  }

  if (done) {
    return (
      <Card>
        <CardHeader className="items-center text-center">
          <div className="mb-2 flex size-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-300">
            <CheckCircle2 className="size-6" aria-hidden />
          </div>
          <h1 className="text-xl font-semibold tracking-tight">Password updated</h1>
          <CardDescription>
            You were signed out everywhere for safety. Sign in with your new password.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild className="w-full">
            <Link to="/login">Go to sign in</Link>
          </Button>
        </CardContent>
      </Card>
    )
  }

  const onSubmit = handleSubmit((values) => {
    setServerError(null)
    reset.mutate({ token, password: values.password })
  })

  return (
    <Card>
      <CardHeader>
        <h1 className="text-xl font-semibold tracking-tight">Choose a new password</h1>
        <CardDescription>Pick something you do not use anywhere else.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={(event) => void onSubmit(event)} noValidate className="space-y-4">
          {serverError ? <FormAlert tone="error">{serverError}</FormAlert> : null}
          <div className="space-y-2">
            <Field label="New password" error={errors.password?.message}>
              {(a11y) => (
                <PasswordInput
                  {...a11y}
                  {...register("password")}
                  autoComplete="new-password"
                  autoFocus
                />
              )}
            </Field>
            <PasswordStrength password={watched} />
          </div>
          <Field label="Confirm new password" error={errors.confirm_password?.message}>
            {(a11y) => (
              <PasswordInput
                {...a11y}
                {...register("confirm_password")}
                autoComplete="new-password"
              />
            )}
          </Field>
          <Button type="submit" className="w-full" disabled={reset.isPending}>
            {reset.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Updating…
              </>
            ) : (
              "Update password"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
