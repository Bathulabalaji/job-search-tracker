import * as Haptics from "expo-haptics"
import { Platform } from "react-native"

const enabled = Platform.OS === "ios" || Platform.OS === "android"

/** Tiny, optional feedback. Silent on the web preview and never throws. */
export const haptics = {
  tap: () => {
    if (enabled) void Haptics.selectionAsync().catch(() => undefined)
  },
  light: () => {
    if (enabled) void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => undefined)
  },
  success: () => {
    if (enabled)
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined)
  },
  error: () => {
    if (enabled)
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => undefined)
  },
}
