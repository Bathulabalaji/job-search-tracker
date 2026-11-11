import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { useRouter } from "expo-router"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { authApi } from "@/api/auth"
import { ApiError, retryMessage } from "@/api/client"
import { AuthShell, FormAlert } from "@/components/auth/auth-shell"
import { Button } from "@/components/ui/button"
import { FormText } from "@/components/ui/form"
import { emailField } from "@/features/auth/email-schema"

const schema = z.object({ email: emailField })
type Values = z.infer<typeof schema>

export default function ForgotPasswordScreen() {
  const router = useRouter()
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { control, handleSubmit } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: "" },
  })
  const send = useMutation({
    mutationFn: (v: Values) => authApi.forgotPassword(v.email.trim().toLowerCase()),
    onSuccess: (r) => setMessage(r.message),
    onError: (e: Error) => setError(e instanceof ApiError ? retryMessage(e) : "Something went wrong."),
  })

  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter your email and we'll send you a reset link."
    >
      {message ? (
        <FormAlert tone="success" message={`${message} The link opens in your browser, where you can choose a new password. Then sign in here.`} />
      ) : null}
      {error ? <FormAlert message={error} /> : null}
      <FormText
        control={control}
        name="email"
        label="Email"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="email-address"
        textContentType="emailAddress"
      />
      <Button
        label={message ? "Send again" : "Send reset link"}
        loading={send.isPending}
        onPress={handleSubmit((v) => {
          setError(null)
          send.mutate(v)
        })}
      />
      <Button label="Back to sign in" variant="ghost" onPress={() => router.replace("/login")} />
    </AuthShell>
  )
}
