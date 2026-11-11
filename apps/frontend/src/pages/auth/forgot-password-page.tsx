import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { ArrowLeft, Loader2, MailCheck } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link } from "react-router-dom"
import { z } from "zod"

import { authApi } from "@/api/auth"
import { ApiError, retryMessage } from "@/api/client"
import { FormAlert } from "@/components/auth/form-alert"
import { Field } from "@/components/form/field"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { emailField } from "@/features/auth/email-schema"

const schema = z.object({ email: emailField })
type Values = z.infer<typeof schema>

export function ForgotPasswordPage() {
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "" } })

  const forgot = useMutation({
    mutationFn: (email: string) => authApi.forgotPassword(email),
    onSuccess: (_data, email) => setSentTo(email),
    onError: (error: Error) =>
      setServerError(
        error instanceof ApiError ? retryMessage(error) : "Something went wrong. Please try again.",
      ),
  })

  const onSubmit = handleSubmit((values) => {
    setServerError(null)
    forgot.mutate(values.email)
  })

  if (sentTo) {
    return (
      <Card>
        <CardHeader className="items-center text-center">
          <div className="mb-2 flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
            <MailCheck className="size-6" aria-hidden />
          </div>
          <h1 className="text-xl font-semibold tracking-tight">Check your email</h1>
          <CardDescription>
            If an account exists for <strong className="text-foreground">{sentTo}</strong>, we have
            sent a link to reset the password. It works for 30 minutes.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-center">
          <p className="text-sm text-muted-foreground">
            Nothing after a few minutes? Check spam, or make sure you used the address you signed up
            with.
          </p>
          <Button variant="outline" className="w-full" onClick={() => setSentTo(null)}>
            Use a different email
          </Button>
          <Link
            to="/login"
            className="inline-block text-sm font-medium text-primary hover:underline"
          >
            Back to sign in
          </Link>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <h1 className="text-xl font-semibold tracking-tight">Forgot your password?</h1>
        <CardDescription>
          Enter your email and we will send you a link to choose a new one.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <form onSubmit={(event) => void onSubmit(event)} noValidate className="space-y-4">
          {serverError ? <FormAlert tone="error">{serverError}</FormAlert> : null}
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
          <Button type="submit" className="w-full" disabled={forgot.isPending}>
            {forgot.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Sending…
              </>
            ) : (
              "Send reset link"
            )}
          </Button>
        </form>
        <Link
          to="/login"
          className="flex items-center justify-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          <ArrowLeft className="size-4" aria-hidden />
          Back to sign in
        </Link>
      </CardContent>
    </Card>
  )
}
