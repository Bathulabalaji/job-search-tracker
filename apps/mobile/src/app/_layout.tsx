import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import {
  DarkTheme,
  DefaultTheme,
  Stack,
  ThemeProvider as NavigationThemeProvider,
} from "expo-router"
import * as SplashScreen from "expo-splash-screen"
import { StatusBar } from "expo-status-bar"
import { useEffect, useState } from "react"
import { ActivityIndicator, View } from "react-native"
import { GestureHandlerRootView } from "react-native-gesture-handler"
import { SafeAreaProvider } from "react-native-safe-area-context"

import { ApiError } from "@/api/client"
import { ErrorState } from "@/components/ui/states"
import { ToastHost } from "@/components/ui/toast-host"
import { useAuth } from "@/features/auth/auth-context"
import { AuthProvider } from "@/features/auth/auth-provider"
import { ThemeProvider, useTheme } from "@/theme/theme"

void SplashScreen.preventAutoHideAsync()

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // Retry network blips and sleeping servers, but never a 4xx: that will not fix itself.
        retry: (count, error) =>
          !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
        refetchOnWindowFocus: false,
      },
    },
  })
}

export default function RootLayout() {
  const [queryClient] = useState(makeQueryClient)
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider>
            <AuthProvider>
              <Shell />
            </AuthProvider>
          </ThemeProvider>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  )
}

function Shell() {
  const { colors, isDark } = useTheme()
  const { state, refresh } = useAuth()

  useEffect(() => {
    if (state.status !== "loading") void SplashScreen.hideAsync()
  }, [state.status])

  const navTheme = {
    ...(isDark ? DarkTheme : DefaultTheme),
    colors: {
      ...(isDark ? DarkTheme : DefaultTheme).colors,
      primary: colors.primary,
      background: colors.bg,
      card: colors.surface,
      text: colors.text,
      border: colors.border,
    },
  }

  if (state.status === "loading") {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    )
  }
  if (state.status === "error") {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: "center" }}>
        <ErrorState
          title="We couldn't reach the server"
          error={new Error(state.message)}
          onRetry={() => void refresh()}
        />
      </View>
    )
  }

  const signedIn = state.status === "authenticated"
  return (
    <NavigationThemeProvider value={navTheme}>
      <StatusBar style={isDark ? "light" : "dark"} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }}>
        <Stack.Protected guard={signedIn}>
          <Stack.Screen name="(app)" />
        </Stack.Protected>
        <Stack.Protected guard={!signedIn}>
          <Stack.Screen name="(auth)" />
        </Stack.Protected>
      </Stack>
      <ToastHost />
    </NavigationThemeProvider>
  )
}
