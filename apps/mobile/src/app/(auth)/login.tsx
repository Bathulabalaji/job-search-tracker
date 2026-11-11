import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { Link, useRouter } from "expo-router"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { View } from "react-native"
import { z } from "zod"

import { authApi } from "@/api/auth"
import { ApiError, retryMessage } from "@/api/client"
import { AuthShell, FormAlert, OrDivider } from "@/components/auth/auth-shell"
import { Button } from "@/components/ui/button"
import { FormText } from "@/components/ui/form"
import { Text } from "@/components/ui/text"
import { useAuth } from "@/features/auth/auth-context"
import { emailField } from "@/features/auth/email-schema"
import { GoogleSignInButton, googleSignInAvailable } from "@/features/auth/google-sign-in"
import { toast } from "@/lib/toast-bus"

const schema = z.object({ email: emailField, password: z.string().min(1, "Enter your password") })
type Values = z.infer<typeof schema>

export default function LoginScreen() {
  const { signIn } = useAuth()
  const router = useRouter()
  const [formError, setFormError] = useState<{ code?: string; message: string } | null>(null)
  const { control, handleSubmit, getValues } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  })

  const login = useMutation({
    mutationFn: authApi.login,
    onSuccess: (response) => signIn(response),
    onError: (error: Error) => {
      setFormError(
        error instanceof ApiError
          ? { code: error.code, message: retryMessage(error) }
          : { message: "Something went wrong. Please try again." },
      )
    },
  })

  const submit = handleSubmit((v) => {
    setFormError(null)
    login.mutate(v)
  })

  const resend = useMutation({
    mutationFn: () => authApi.resendVerification(getValues("email")),
    onSuccess: (r) => toast.success("Check your inbox", r.message),
    onError: (e: Error) => toast.error("Could not send email", e.message),
  })

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to pick up where you left off.">
      {formError ? <FormAlert message={formError.message} /> : null}
      {formError?.code === "email_not_verified" ? (
        <Button
          label="Resend verification email"
          variant="secondary"
          icon="mail-outline"
          loading={resend.isPending}
          onPress={() => resend.mutate()}
        />
      ) : null}

      <FormText
        control={control}
        name="email"
        label="Email"
        autoCapitalize="none"
        autoComplete="email"
        autoCorrect={false}
        keyboardType="email-address"
        textContentType="emailAddress"
        returnKeyType="next"
      />
      <FormText
        control={control}
        name="password"
        label="Password"
        secureToggle
        autoCapitalize="none"
        autoComplete="current-password"
        textContentType="password"
        returnKeyType="go"
        onSubmitEditing={() => void submit()}
      />
      <View style={{ alignItems: "flex-end" }}>
        <Link href="/forgot-password" accessibilityRole="link">
          <Text variant="small" tone="primary" style={{ fontWeight: "600" }}>
            Forgot password?
          </Text>
        </Link>
      </View>
      <Button
        label="Sign in"
        loading={login.isPending}
        onPress={() => void submit()}
      />

      {googleSignInAvailable ? (
        <>
          <OrDivider />
          <GoogleSignInButton
            label="Continue with Google"
            onSuccess={(r) => void signIn(r)}
            onError={(m) => setFormError({ message: m })}
          />
        </>
      ) : null}

      <View style={{ flexDirection: "row", justifyContent: "center", gap: 6, marginTop: 8 }}>
        <Text tone="muted">New here?</Text>
        <Text tone="primary" style={{ fontWeight: "600" }} onPress={() => router.push("/register")}>
          Create an account
        </Text>
      </View>
    </AuthShell>
  )
}
