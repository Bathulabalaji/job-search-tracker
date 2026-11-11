import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { Loader2, MailCheck } from "lucide-react"
import { useEffect, useState } from "react"
import { Controller, useForm, useWatch } from "react-hook-form"
import { Link } from "react-router-dom"
import { toast } from "sonner"
import { z } from "zod"

import { authApi } from "@/api/auth"
import { ApiError, retryMessage } from "@/api/client"
import { FormAlert } from "@/components/auth/form-alert"
import { PasswordInput } from "@/components/auth/password-input"
import { PasswordStrength } from "@/components/auth/password-strength"
import { Field } from "@/components/form/field"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuth } from "@/features/auth/auth-context"
import { emailField } from "@/features/auth/email-schema"
import { GoogleSignInButton } from "@/features/auth/google-button"
import { passwordProblem } from "@/features/auth/password-policy"
import { GOOGLE_CLIENT_ID, PRIVACY_URL, TERMS_URL } from "@/lib/env"

const schema = z
  .object({
    full_name: z.string().trim().min(1, "Enter your full name").max(100, "Name is too long"),
    email: emailField,
    password: z.string().min(1, "Choose a password"),
    confirm_password: z.string().min(1, "Confirm your password"),
    accept_terms: z.boolean(),
  })
  .superRefine((values, ctx) => {
    const problem = values.password
      ? passwordProblem(values.password, { email: values.email, fullName: values.full_name })
      : null
    if (problem) ctx.addIssue({ code: "custom", path: ["password"], message: problem })
    if (values.confirm_password && values.password !== values.confirm_password) {
      ctx.addIssue({
        code: "custom",
        path: ["confirm_password"],
        message: "Passwords do not match",
      })
    }
    if (!values.accept_terms) {
      ctx.addIssue({
        code: "custom",
        path: ["accept_terms"],
        message: "You must accept the terms to create an account",
      })
    }
  })
type Values = z.infer<typeof schema>

const RESEND_COOLDOWN_SECONDS = 30

function TermsLabel() {
  const link = (href: string, text: string) =>
    href ? (
      <a href={href} target="_blank" rel="noreferrer noopener" className="text-primary underline">
        {text}
      </a>
    ) : (
      text
    )
  return (
    <>
      I agree to the {link(TERMS_URL, "terms of use")} and {link(PRIVACY_URL, "privacy policy")}
    </>
  )
}

function CheckEmail({ email }: { email: string }) {
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_SECONDS)
  const resend = useMutation({
    mutationFn: () => authApi.resendVerification(email),
    onSuccess: () => {
      toast.success("Verification email sent again.")
      setCooldown(RESEND_COOLDOWN_SECONDS)
    },
    onError: (error: Error) =>
      toast.error(error instanceof ApiError ? retryMessage(error) : "Could not send the email."),
  })

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [cooldown])

  return (
    <Card>
      <CardHeader className="items-center text-center">
        <div className="mb-2 flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <MailCheck className="size-6" aria-hidden />
        </div>
        <h1 className="text-xl font-semibold tracking-tight">Check your email</h1>
        <CardDescription>
          We sent a verification link to <strong className="text-foreground">{email}</strong>. Open
          it to activate your account.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-center">
        <p className="text-sm text-muted-foreground">
          The link works for 24 hours. Cannot find it? Check your spam folder.
        </p>
        <Button
          type="button"
          variant="outline"
          className="w-full"
          disabled={cooldown > 0 || resend.isPending}
          onClick={() => resend.mutate()}
        >
          {resend.isPending
            ? "Sending…"
            : cooldown > 0
              ? `Resend email in ${cooldown}s`
              : "Resend verification email"}
        </Button>
        <Link to="/login" className="inline-block text-sm font-medium text-primary hover:underline">
          Back to sign in
        </Link>
      </CardContent>
    </Card>
  )
}

export function RegisterPage() {
  const { signIn } = useAuth()
  const [registeredEmail, setRegisteredEmail] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    control,
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      full_name: "",
      email: "",
      password: "",
      confirm_password: "",
      accept_terms: false,
    },
  })

  const watched = useWatch({ control, name: "password" })

  const registerAccount = useMutation({
    mutationFn: authApi.register,
    onSuccess: (_data, variables) => setRegisteredEmail(variables.email),
    onError: (error: Error) => {
      if (error instanceof ApiError && error.code === "email_taken") {
        setError("email", { message: "An account with this email already exists. Try signing in." })
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

  const onSubmit = handleSubmit((values) => {
    setServerError(null)
    registerAccount.mutate({
      full_name: values.full_name,
      email: values.email,
      password: values.password,
      accept_terms: values.accept_terms,
    })
  })

  if (registeredEmail) return <CheckEmail email={registeredEmail} />

  return (
    <Card>
      <CardHeader>
        <h1 className="text-xl font-semibold tracking-tight">Create your account</h1>
        <CardDescription>
          Track every opportunity, follow-up and interview in one place.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <GoogleSignInButton text="signup_with" onSuccess={signIn} />
        {GOOGLE_CLIENT_ID ? (
          <>
            <p className="text-center text-xs text-muted-foreground">
              Continuing with Google means you agree to the terms of use and privacy policy.
            </p>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="h-px flex-1 bg-border" />
              or sign up with email
              <span className="h-px flex-1 bg-border" />
            </div>
          </>
        ) : null}

        <form onSubmit={(event) => void onSubmit(event)} noValidate className="space-y-4">
          {serverError ? <FormAlert tone="error">{serverError}</FormAlert> : null}

          <Field label="Full name" error={errors.full_name?.message}>
            {(a11y) => <Input {...a11y} {...register("full_name")} autoComplete="name" autoFocus />}
          </Field>
          <Field label="Email" error={errors.email?.message}>
            {(a11y) => (
              <Input
                {...a11y}
                {...register("email")}
                type="email"
                autoComplete="email"
                inputMode="email"
              />
            )}
          </Field>
          <div className="space-y-2">
            <Field label="Password" error={errors.password?.message}>
              {(a11y) => (
                <PasswordInput {...a11y} {...register("password")} autoComplete="new-password" />
              )}
            </Field>
            <PasswordStrength password={watched} />
          </div>
          <Field label="Confirm password" error={errors.confirm_password?.message}>
            {(a11y) => (
              <PasswordInput
                {...a11y}
                {...register("confirm_password")}
                autoComplete="new-password"
              />
            )}
          </Field>

          <div className="space-y-1.5">
            <div className="flex items-start gap-2.5">
              <Controller
                control={control}
                name="accept_terms"
                render={({ field }) => (
                  <Checkbox
                    id="accept_terms"
                    checked={field.value}
                    onCheckedChange={(checked) => field.onChange(checked === true)}
                    aria-invalid={Boolean(errors.accept_terms)}
                    className="mt-0.5"
                  />
                )}
              />
              <Label htmlFor="accept_terms" className="text-sm leading-snug font-normal">
                <TermsLabel />
              </Label>
            </div>
            {errors.accept_terms ? (
              <p className="text-xs text-destructive">{errors.accept_terms.message}</p>
            ) : null}
          </div>

          <Button type="submit" className="w-full" disabled={registerAccount.isPending}>
            {registerAccount.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Creating account…
              </>
            ) : (
              "Create account"
            )}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  )
}
