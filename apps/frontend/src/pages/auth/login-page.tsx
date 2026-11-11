import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link } from "react-router-dom"
import { toast } from "sonner"
import { z } from "zod"

import { authApi } from "@/api/auth"
import { ApiError, retryMessage } from "@/api/client"
import { FormAlert } from "@/components/auth/form-alert"
import { PasswordInput } from "@/components/auth/password-input"
import { Field } from "@/components/form/field"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useAuth } from "@/features/auth/auth-context"
import { emailField } from "@/features/auth/email-schema"
import { GoogleSignInButton } from "@/features/auth/google-button"
import { GOOGLE_CLIENT_ID } from "@/lib/env"

const schema = z.object({
  email: emailField,
  password: z.string().min(1, "Enter your password"),
})
type Values = z.infer<typeof schema>

interface ServerError {
  code: string | undefined
  message: string
}

export function LoginPage() {
  const { state, signIn } = useAuth()
  const [serverError, setServerError] = useState<ServerError | null>(null)
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } })

  const login = useMutation({
    mutationFn: authApi.login,
    onSuccess: signIn,
    onError: (error: Error) => {
      setServerError(
        error instanceof ApiError
          ? { code: error.code, message: retryMessage(error) }
          : { code: undefined, message: "Something went wrong. Please try again." },
      )
    },
  })

  const resend = useMutation({
    mutationFn: () => authApi.resendVerification(getValues("email").trim()),
    onSuccess: () =>
      toast.success("If that account needs it, a new verification email is on its way."),
    onError: (error: Error) =>
      toast.error(error instanceof ApiError ? retryMessage(error) : "Could not send the email."),
  })

  const onSubmit = handleSubmit((values) => {
    setServerError(null)
    login.mutate({ email: values.email, password: values.password })
  })

  return (
    <Card>
      <CardHeader>
        <h1 className="text-xl font-semibold tracking-tight">Welcome back</h1>
        <CardDescription>Sign in to your job search workspace.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {state.status === "unauthenticated" && state.expired ? (
          <FormAlert tone="info">Your session expired. Please sign in again.</FormAlert>
        ) : null}

        <GoogleSignInButton text="signin_with" onSuccess={signIn} />
        {GOOGLE_CLIENT_ID ? (
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            or sign in with email
            <span className="h-px flex-1 bg-border" />
          </div>
        ) : null}

        <form onSubmit={(event) => void onSubmit(event)} noValidate className="space-y-4">
          {serverError ? (
            <FormAlert tone="error">
              <p>{serverError.message}</p>
              {serverError.code === "email_not_verified" ? (
                <Button
                  type="button"
                  variant="link"
                  className="h-auto p-0"
                  disabled={resend.isPending}
                  onClick={() => resend.mutate()}
                >
                  {resend.isPending ? "Sending…" : "Resend verification email"}
                </Button>
              ) : null}
            </FormAlert>
          ) : null}

          <Field label="Email" error={errors.email?.message}>
            {(a11y) => (
              <Input
                {...a11y}
                {...register("email")}
                type="email"
                autoComplete="email"
                inputMode="email"
                autoFocus
              />
            )}
          </Field>
          <Field label="Password" error={errors.password?.message}>
            {(a11y) => (
              <PasswordInput {...a11y} {...register("password")} autoComplete="current-password" />
            )}
          </Field>

          <div className="flex justify-end">
            <Link
              to="/forgot-password"
              className="rounded-sm text-sm text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
            >
              Forgot password?
            </Link>
          </div>

          <Button type="submit" className="w-full" disabled={login.isPending}>
            {login.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Signing in…
              </>
            ) : (
              "Sign in"
            )}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          New here?{" "}
          <Link to="/register" className="font-medium text-primary hover:underline">
            Create an account
          </Link>
        </p>
      </CardContent>
    </Card>
  )
}
