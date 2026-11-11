import Constants from "expo-constants"
import { useState } from "react"
import { Alert, Linking, View } from "react-native"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Screen, SectionHeader } from "@/components/ui/screen"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Text } from "@/components/ui/text"
import { WEB_URL } from "@/config/env"
import { useAuth, useUser } from "@/features/auth/auth-context"
import { ChangePasswordSheet, EditNameSheet } from "@/features/auth/account-forms"
import { toast } from "@/lib/toast-bus"
import { useTheme, type ThemePreference } from "@/theme/theme"

const THEME_OPTIONS = [
  { value: "system", label: "System" },
  { value: "dark", label: "Dark" },
  { value: "light", label: "Light" },
] as const

export default function AccountScreen() {
  const user = useUser()
  const { signOut, signOutEverywhere } = useAuth()
  const { preference, setPreference } = useTheme()
  const [editingName, setEditingName] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)

  const confirmSignOut = () =>
    Alert.alert("Sign out?", "You'll need to sign in again on this device.", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign out", style: "destructive", onPress: () => void signOut() },
    ])

  const confirmSignOutEverywhere = () =>
    Alert.alert("Sign out everywhere?", "This ends your session on every device, including this one.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Sign out everywhere",
        style: "destructive",
        onPress: () => void signOutEverywhere().catch((e: Error) => toast.error("Could not sign out", e.message)),
      },
    ])

  return (
    <Screen edges={[]}>
      <Card style={{ gap: 6 }}>
        <Text variant="heading">{user.full_name}</Text>
        <Text tone="muted">{user.email}</Text>
        <View style={{ flexDirection: "row", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
          {user.email_verified ? <Badge label="Email verified" tone="success" /> : null}
          {user.google_linked ? <Badge label="Google linked" tone="primary" /> : null}
        </View>
        <View style={{ marginTop: 8 }}>
          <Button label="Edit name" icon="create-outline" variant="secondary" size="sm" fullWidth={false} onPress={() => setEditingName(true)} />
        </View>
      </Card>

      <View style={{ gap: 10 }}>
        <SectionHeader title="Appearance" />
        <SegmentedControl options={THEME_OPTIONS} value={preference} onChange={(v: ThemePreference) => setPreference(v)} />
      </View>

      <View style={{ gap: 10 }}>
        <SectionHeader title="Security" />
        {user.has_password ? (
          <Button label="Change password" icon="key-outline" variant="secondary" onPress={() => setChangingPassword(true)} />
        ) : (
          <Card>
            <Text variant="small" tone="muted">
              You signed up with Google, so there's no password yet. To set one, use "Forgot password" on the sign-in screen.
            </Text>
          </Card>
        )}
        <Button label="Sign out everywhere" icon="shield-outline" variant="secondary" onPress={confirmSignOutEverywhere} />
        <Button label="Sign out" icon="log-out-outline" variant="danger" onPress={confirmSignOut} />
      </View>

      <View style={{ gap: 6, alignItems: "center", marginTop: 8 }}>
        <Text variant="caption" tone="muted" onPress={() => void Linking.openURL(WEB_URL)}>
          Open the website
        </Text>
        <Text variant="caption" tone="muted">
          Jobs Tracker {Constants.expoConfig?.version ?? ""}
        </Text>
      </View>

      <EditNameSheet visible={editingName} user={user} onClose={() => setEditingName(false)} />
      <ChangePasswordSheet visible={changingPassword} onClose={() => setChangingPassword(false)} />
    </Screen>
  )
}
