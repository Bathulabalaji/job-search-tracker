import { useMutation } from "@tanstack/react-query"
import { CheckCircle2, Loader2, MailWarning } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"

import { authApi } from "@/api/auth"
import { ApiError, retryMessage } from "@/api/client"
import { FormAlert } from "@/components/auth/form-alert"
import { Field } from "@/components/form/field"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useHashToken } from "@/features/auth/use-hash-token"

type Status =
  | { kind: "verifying" }
  | { kind: "success" }
  | { kind: "failed"; code: string | undefined; message: string }

function ResendForm() {
  const [email, setEmail] = useState("")
  const [error, setError] = useState<string | null>(null)
  const resend = useMutation({
    mutationFn: () => authApi.resendVerification(email.trim()),
    onSuccess: () => toast.success("If that account needs it, a new link is on its way."),
    onError: (e: Error) => setError(e instanceof ApiError ? retryMessage(e) : "Could not send."),
  })
  const valid = /^\S+@\S+\.\S+$/.test(email.trim())

  return (
    <form
      className="space-y-3 text-left"
      onSubmit={(event) => {
        event.preventDefault()
        setError(null)
        if (valid) resend.mutate()
      }}
    >
      {error ? <FormAlert tone="error">{error}</FormAlert> : null}
      <Field label="Email address">
        {(a11y) => (
          <Input
            {...a11y}
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
          />
        )}
      </Field>
      <Button type="submit" className="w-full" disabled={!valid || resend.isPending}>
        {resend.isPending ? "Sending…" : "Send a new verification link"}
      </Button>
    </form>
  )
}

export function VerifyEmailPage() {
  const { token, attempt } = useHashToken()
  // A new link in the same tab remounts the content, so it verifies afresh.
  return <VerifyEmailContent key={attempt} token={token} />
}

function VerifyEmailContent({ token }: { token: string | null }) {
  const [status, setStatus] = useState<Status>(
    token
      ? { kind: "verifying" }
      : {
          kind: "failed",
          code: "invalid_token",
          message: "The verification link is missing or incomplete.",
        },
  )
  // React StrictMode runs effects twice in development; the token is single-use.
  const started = useRef(false)

  useEffect(() => {
    if (!token || started.current) return
    started.current = true
    authApi
      .verifyEmail(token)
      .then(() => setStatus({ kind: "success" }))
      .catch((error: unknown) => {
        setStatus(
          error instanceof ApiError
            ? { kind: "failed", code: error.code, message: retryMessage(error) }
            : {
                kind: "failed",
                code: undefined,
                message: "Something went wrong. Please try again.",
              },
        )
      })
  }, [token])

  if (status.kind === "verifying") {
    return (
      <Card role="status" aria-live="polite">
        <CardHeader className="items-center text-center">
          <Loader2 className="mb-2 size-8 animate-spin text-primary" aria-hidden />
          <h1 className="text-xl font-semibold tracking-tight">Verifying your email…</h1>
          <CardDescription>This only takes a moment.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (status.kind === "success") {
    return (
      <Card>
        <CardHeader className="items-center text-center">
          <div className="mb-2 flex size-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-300">
            <CheckCircle2 className="size-6" aria-hidden />
          </div>
          <h1 className="text-xl font-semibold tracking-tight">Email verified</h1>
          <CardDescription>Your account is ready. You can sign in now.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild className="w-full">
            <Link to="/login">Continue to sign in</Link>
          </Button>
        </CardContent>
      </Card>
    )
  }

  const alreadyUsed = status.code === "token_used"
  return (
    <Card>
      <CardHeader className="items-center text-center">
        <div className="mb-2 flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
          <MailWarning className="size-6" aria-hidden />
        </div>
        <h1 className="text-xl font-semibold tracking-tight">
          {status.code === "token_expired" ? "This link has expired" : "Verification failed"}
        </h1>
        <CardDescription>{status.message}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {alreadyUsed ? (
          <p className="text-center text-sm text-muted-foreground">
            If you already verified your email, you can just sign in.
          </p>
        ) : null}
        <ResendForm />
        <div className="text-center">
          <Link to="/login" className="text-sm font-medium text-primary hover:underline">
            Back to sign in
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
