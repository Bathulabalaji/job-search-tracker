import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { useRouter } from "expo-router"
import { useState } from "react"
import { Controller, useForm, useWatch } from "react-hook-form"
import { Pressable, View } from "react-native"
import { z } from "zod"

import { authApi } from "@/api/auth"
import { ApiError, retryMessage } from "@/api/client"
import { AuthShell, FormAlert, OrDivider } from "@/components/auth/auth-shell"
import { Button } from "@/components/ui/button"
import { FormText } from "@/components/ui/form"
import { Icon } from "@/components/ui/icon"
import { Text } from "@/components/ui/text"
import { useAuth } from "@/features/auth/auth-context"
import { emailField } from "@/features/auth/email-schema"
import { GoogleSignInButton, googleSignInAvailable } from "@/features/auth/google-sign-in"
import { passwordChecks, passwordProblem } from "@/features/auth/password-policy"
import { WEB_URL } from "@/config/env"
import { Linking } from "react-native"

const schema = z
  .object({
    full_name: z.string().trim().min(1, "Enter your full name").max(100),
    email: emailField,
    password: z.string().min(1, "Choose a password"),
    confirm: z.string().min(1, "Repeat your password"),
    accept_terms: z.boolean().refine((v) => v, "Please accept the terms to continue"),
  })
  .superRefine((v, ctx) => {
    const problem = passwordProblem(v.password, { email: v.email, fullName: v.full_name })
    if (problem) ctx.addIssue({ code: "custom", path: ["password"], message: problem })
    if (v.confirm && v.password !== v.confirm)
      ctx.addIssue({ code: "custom", path: ["confirm"], message: "Passwords do not match" })
  })
type Values = z.infer<typeof schema>

export default function RegisterScreen() {
  const router = useRouter()
  const { signIn } = useAuth()
  const [formError, setFormError] = useState<string | null>(null)
  const [sentTo, setSentTo] = useState<string | null>(null)
  const { control, handleSubmit } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", email: "", password: "", confirm: "", accept_terms: false },
  })
  const password = useWatch({ control, name: "password" })

  const register = useMutation({
    mutationFn: (v: Values) =>
      authApi.register({
        full_name: v.full_name,
        email: v.email.trim().toLowerCase(),
        password: v.password,
        accept_terms: v.accept_terms,
      }),
    onSuccess: (_r, v) => setSentTo(v.email.trim().toLowerCase()),
    onError: (error: Error) =>
      setFormError(error instanceof ApiError ? retryMessage(error) : "Something went wrong."),
  })

  if (sentTo) {
    return (
      <AuthShell title="Check your email" subtitle={`We sent a verification link to ${sentTo}.`}>
        <FormAlert
          tone="success"
          message="Open the link in that email to verify your address, then come back here and sign in."
        />
        <Button label="Back to sign in" onPress={() => router.replace("/login")} />
      </AuthShell>
    )
  }

  return (
    <AuthShell title="Create your account" subtitle="Track every opportunity in one place.">
      {formError ? <FormAlert message={formError} /> : null}
      <FormText control={control} name="full_name" label="Full name" autoComplete="name" textContentType="name" autoCapitalize="words" />
      <FormText
        control={control}
        name="email"
        label="Email"
        autoCapitalize="none"
        autoComplete="email"
        autoCorrect={false}
        keyboardType="email-address"
        textContentType="emailAddress"
      />
      <FormText
        control={control}
        name="password"
        label="Password"
        secureToggle
        autoCapitalize="none"
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <View style={{ gap: 4 }} accessibilityLabel="Password requirements">
        {passwordChecks(password).map((check) => (
          <View key={check.label} style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Icon
              name={check.met ? "checkmark-circle" : "ellipse-outline"}
              size={16}
              color={check.met ? "success" : "muted"}
            />
            <Text variant="caption" tone={check.met ? "success" : "muted"}>
              {check.label}
            </Text>
          </View>
        ))}
      </View>
      <FormText control={control} name="confirm" label="Confirm password" secureToggle autoCapitalize="none" textContentType="newPassword" />

      <Controller
        control={control}
        name="accept_terms"
        render={({ field, fieldState }) => (
          <View style={{ gap: 4 }}>
            <Pressable
              accessibilityRole="checkbox"
              accessibilityState={{ checked: field.value }}
              onPress={() => field.onChange(!field.value)}
              style={{ flexDirection: "row", gap: 10, alignItems: "center", minHeight: 44 }}
            >
              <Icon name={field.value ? "checkbox" : "square-outline"} size={24} color={field.value ? "primary" : "muted"} />
              <Text style={{ flex: 1 }} variant="small">
                I agree to the{" "}
                <Text variant="small" tone="primary" onPress={() => void Linking.openURL(`${WEB_URL}/`)}>
                  terms of use and privacy policy
                </Text>
              </Text>
            </Pressable>
            {fieldState.error ? (
              <Text variant="caption" tone="danger">
                {fieldState.error.message}
              </Text>
            ) : null}
          </View>
        )}
      />

      <Button
        label="Create account"
        loading={register.isPending}
        onPress={handleSubmit((v) => {
          setFormError(null)
          register.mutate(v)
        })}
      />

      {googleSignInAvailable ? (
        <>
          <OrDivider />
          <GoogleSignInButton
            label="Sign up with Google"
            onSuccess={(r) => void signIn(r)}
            onError={setFormError}
          />
        </>
      ) : null}

      <View style={{ flexDirection: "row", justifyContent: "center", gap: 6, marginTop: 8 }}>
        <Text tone="muted">Already have an account?</Text>
        <Text tone="primary" style={{ fontWeight: "600" }} onPress={() => router.replace("/login")}>
          Sign in
        </Text>
      </View>
    </AuthShell>
  )
}
