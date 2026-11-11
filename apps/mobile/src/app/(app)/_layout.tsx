import { Stack } from "expo-router"

import { useTheme } from "@/theme/theme"

/** Pushed screens use the native header (back swipe, large titles); tabs hide it. */
export default function AppLayout() {
  const { colors } = useTheme()
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.primary,
        headerTitleStyle: { color: colors.text },
        headerShadowVisible: false,
        headerBackButtonDisplayMode: "minimal",
        contentStyle: { backgroundColor: colors.bg },
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="opportunity/[id]" options={{ title: "" }} />
      <Stack.Screen
        name="opportunity/form"
        options={{ presentation: "modal", title: "New opportunity" }}
      />
      <Stack.Screen name="prep" options={{ title: "Interview prep" }} />
      <Stack.Screen name="contacts" options={{ title: "Contacts & Resumes" }} />
      <Stack.Screen name="account" options={{ title: "Account" }} />
    </Stack>
  )
}
